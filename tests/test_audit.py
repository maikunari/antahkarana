"""The audit and purge CLI: finds secrets stored before the keeper existed, and removes them."""

from __future__ import annotations

import json

import pytest
import zvec

from secret_samples import a_secret_sentence, positives
from src.chitta.schema import init_db
from src.chitta.store import DISSOLVED_CONTENT, ChittaStore
from src.dvarapala.__main__ import main
from src.dvarapala.audit import EmbedderRequired, audit, purge
from src.dvarapala.keeper import default_keeper

SAMPLE = a_secret_sentence()
SECRET = SAMPLE.values[0]
BARE = next(s for s in positives() if s.label == "github-pat").values[0]
OLD = "the-old-dissolved-text-3b9e"


def _insert_memory(db, vec, memory_id, content, state="active", source_agent=None):
    db.execute(
        """INSERT INTO memories (id, content, scope, categories, source_agent, state,
        embedding_id, created_at, updated_at) VALUES (?, ?, '/p', '["decision"]', ?, ?, ?, ?, ?)""",
        (memory_id, content, source_agent, state, memory_id, f"2026-01-0{len(memory_id)}", "x"),
    )
    vec.insert(zvec.Doc(id=memory_id, vectors={"embedding": [0.5] * 768}))


@pytest.fixture
def seeded(tmp_path):
    """A data dir written before the keeper: secrets in memories, the log, and feedback."""
    data = tmp_path / "data"
    chitta = ChittaStore(data)
    chitta.init()
    db, vec = chitta._db, chitta._vec
    _insert_memory(db, vec, "m1", SAMPLE.text, source_agent="claude-code")
    _insert_memory(db, vec, "m22", f"GITHUB_TOKEN={BARE}")
    _insert_memory(db, vec, "m333", "We chose Postgres for Jozu.")
    _insert_memory(db, vec, "m4444", f"Old dissolved memory {OLD}.", state="dissolved")
    db.execute(
        "INSERT INTO determinations (id, input_text, determination, created_at, memory_id) "
        "VALUES ('d1', ?, ?, '2026-01-01', 'm1')",
        (SAMPLE.text, json.dumps({"gemini": {"response": {"scope": f"/k/{BARE}"}},
                                  "source_agent": "claude-code", "final": {"store": True}})),
    )
    db.execute(
        "INSERT INTO feedback (id, memory_id, feedback_type, context, details, created_at) "
        "VALUES ('f1', 'm333', 'correction', ?, 'fine', '2026-01-02')",
        (f"while pasting {SECRET} into chat",),
    )
    db.commit()
    vec.flush()
    chitta.close()
    return data


def _all_bytes(data):
    return b"".join(p.read_bytes() for p in data.rglob("*") if p.is_file())


def _snapshot(data):
    """Every data file's bytes, minus SQLite's shared-memory index and an empty WAL,
    which even a read-only open recreates."""
    return {
        str(p.relative_to(data)): p.read_bytes()
        for p in sorted(data.rglob("*"))
        if p.is_file() and not p.name.endswith("-shm") and p.stat().st_size
    }


def test_audit_finds_every_secret_without_changing_anything(seeded):
    before = _snapshot(seeded)

    report = audit(seeded / "chitta.db", default_keeper())

    assert {(h.table, h.column, h.row_id) for h in report.hits} == {
        ("memories", "content", "m1"),
        ("memories", "content", "m22"),
        ("determinations", "input_text", "d1"),
        ("determinations", "determination", "d1"),
        ("feedback", "context", "f1"),
    }
    assert report.unpurged_dissolved == ["m4444"]
    kinds = set(report.rotation())
    assert "stripe-access-token" in kinds and len(kinds) >= 2
    text = "\n".join(report.lines())
    assert SECRET not in text and BARE not in text
    assert _snapshot(seeded) == before


def test_purge_removes_every_secret_and_verifies_it(seeded):
    embedded: list[str] = []

    def embed(text):
        embedded.append(text)
        return [0.25] * 768

    before, after, files = purge(seeded, default_keeper(), embed)

    assert not before.clean
    assert after.clean
    assert files == 0
    assert embedded == [SAMPLE.text.replace(SECRET, "[secret:stripe-access-token]")]
    raw = _all_bytes(seeded)
    assert SECRET.encode() not in raw and BARE.encode() not in raw and OLD.encode() not in raw

    db = init_db(seeded / "chitta.db")
    rows = {r["id"]: dict(r) for r in db.execute("SELECT * FROM memories")}
    assert rows["m1"]["content"] == embedded[0] and rows["m1"]["state"] == "active"
    assert rows["m22"]["state"] == "dissolved"  # nothing but the secret: dissolved
    assert rows["m22"]["content"] == DISSOLVED_CONTENT
    assert rows["m333"]["content"] == "We chose Postgres for Jozu."
    assert rows["m4444"]["content"] == DISSOLVED_CONTENT
    db.close()

    chitta = ChittaStore(seeded)
    chitta.init()
    assert sorted(d.id for d in chitta._vec.iter_docs()) == ["m1", "m333"]
    assert chitta._vec.fetch("m1")["m1"].vectors["embedding"][0] == pytest.approx(0.25)
    chitta.close()


def test_purge_changes_nothing_when_it_cannot_re_embed(seeded):
    before = _snapshot(seeded)

    with pytest.raises(EmbedderRequired, match="GEMINI_API_KEY"):
        purge(seeded, default_keeper(), None)

    assert _snapshot(seeded) == before


def test_purge_needs_no_embedder_when_nothing_is_re_embedded(tmp_path):
    # Secret-only memories are dissolved and dissolved ones purged: no new vector either way.
    data = tmp_path / "data"
    chitta = ChittaStore(data)
    chitta.init()
    _insert_memory(chitta._db, chitta._vec, "m22", f"GITHUB_TOKEN={BARE}")
    _insert_memory(chitta._db, chitta._vec, "m4444", f"Old {BARE} memory.", state="dissolved")
    chitta._db.commit()
    chitta._vec.flush()
    chitta.close()

    before, after, files = purge(data, default_keeper(), None)

    assert not before.clean
    assert after.clean and files == 0
    assert BARE.encode() not in _all_bytes(data)


def test_cli_never_prints_a_secret(seeded, capsys, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr("src.dvarapala.__main__.load_dotenv", lambda: None)

    assert main(["audit", "--data-dir", str(seeded)]) == 1
    assert main(["purge", "--data-dir", str(seeded)]) == 2  # no key: nothing changed

    out = capsys.readouterr().out
    assert "memories.content  stripe-access-token  x1" in out
    assert "Nothing changed" in out
    assert SECRET not in out and BARE not in out


def test_cli_audit_of_a_missing_database_is_a_no_op(tmp_path, capsys):
    assert main(["audit", "--data-dir", str(tmp_path / "none")]) == 0
    assert "nothing to audit" in capsys.readouterr().out

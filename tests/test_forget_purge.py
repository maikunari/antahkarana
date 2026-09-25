"""forget reaches every table: dissolving purges the memory's text, vector, log rows and feedback."""

from __future__ import annotations

import json
import sqlite3
import uuid

import pytest

from conftest import FakeEmbeddings, FakeGemini, determination_rows, make_buddhi
from src.chitta.schema import init_db
from src.chitta.store import DISSOLVED_CONTENT, ChittaStore
from src.manas import tools

MARKER = "the-dissolved-memory-marker-7d1c"


@pytest.fixture
def store(tmp_path):
    """A ChittaStore on real SQLite and a real Zvec collection."""
    chitta = ChittaStore(tmp_path / "data")
    chitta.init()
    yield chitta
    chitta.close()


def _remember(store, content, scope=None):
    result = tools.remember(
        content,
        chitta=store,
        buddhi=make_buddhi(FakeGemini(store=True)),
        embeddings=FakeEmbeddings(),
        scope=scope,
    )
    assert result["stored"] is True
    return result["memory_id"]


def _add_feedback(store, memory_id):
    store._db.execute(
        """INSERT INTO feedback (id, memory_id, feedback_type, context, details, created_at)
        VALUES (?, ?, 'correction', ?, ?, 'now')""",
        (str(uuid.uuid4()), memory_id, f"context {MARKER}", f"details {MARKER}"),
    )
    store._db.commit()


def _row(store, memory_id):
    return dict(store._db.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone())


def test_force_dissolve_purges_the_memory_from_every_table(store, tmp_path):
    memory_id = _remember(store, f"We chose Postgres for Jozu; {MARKER}.")
    keep_id = _remember(store, "Mike prefers short replies in Discord.")
    _add_feedback(store, memory_id)

    result = tools.forget(chitta=store, memory_id=memory_id, force_dissolve=True)

    assert result == {"affected": 1, "transitioned_to": "dissolved", "content_purged": True}
    row = _row(store, memory_id)
    assert row["state"] == "dissolved"
    assert row["content"] == DISSOLVED_CONTENT
    assert row["dissolved_at"] and row["dissolved_reason"] == "User-requested forget"
    assert row["scope"] == "/project/test"  # the trace keeps what it was about
    assert store._vec.fetch(memory_id) == {}
    assert store._vec.fetch(keep_id) != {}
    (logged,) = [r for r in determination_rows(store) if r["final"].get("memory_id") == memory_id]
    assert logged["input_text"] == DISSOLVED_CONTENT
    feedback = store._db.execute("SELECT context, details FROM feedback").fetchone()
    assert tuple(feedback) == (None, None)
    # the other memory is untouched
    assert _row(store, keep_id)["content"] == "Mike prefers short replies in Discord."

    # after compaction no data file holds the text, the WAL included
    store.compact()
    files = [p for p in (tmp_path / "data").rglob("*") if p.is_file()]
    assert not [p for p in files if MARKER.encode() in p.read_bytes()]


def test_compaction_removes_dissolved_vectors_and_keeps_live_ones(store):
    gone = _remember(store, "A memory about to be dissolved.")
    kept = _remember(store, "A memory that stays.")
    store.dissolve([gone], "test")

    assert store.compact() == 1

    assert store._vec.fetch(gone) == {}
    assert list(store._vec.fetch(kept)) == [kept]


def test_latent_keeps_content_and_vector(store):
    memory_id = _remember(store, f"Reversible memory {MARKER}.")

    result = tools.forget(chitta=store, memory_id=memory_id)

    assert result["transitioned_to"] == "latent" and result["content_purged"] is False
    row = _row(store, memory_id)
    assert row["state"] == "latent"
    assert MARKER in row["content"]
    assert list(store._vec.fetch(memory_id)) == [memory_id]


def test_force_dissolve_by_scope_purges_the_whole_subtree(store):
    inside = [_remember(store, f"Jozu fact {i}", scope="/project/jozu/arch") for i in range(2)]
    outside = _remember(store, "Friendly Fires fact", scope="/project/ff")

    result = tools.forget(chitta=store, scope="/project/jozu", force_dissolve=True)

    assert result["affected"] == 2
    assert all(_row(store, i)["content"] == DISSOLVED_CONTENT for i in inside)
    assert _row(store, outside)["content"] == "Friendly Fires fact"
    # already dissolved rows are not counted again
    assert tools.forget(chitta=store, scope="/project/jozu", force_dissolve=True)["affected"] == 0


def test_secure_delete_is_on(store):
    assert store._db.execute("PRAGMA secure_delete").fetchone()[0] == 1


def test_an_older_database_gains_the_memory_link(tmp_path):
    db_path = tmp_path / "chitta.db"
    old = sqlite3.connect(db_path)
    old.executescript(
        """CREATE TABLE determinations (
            id TEXT PRIMARY KEY, input_text TEXT NOT NULL, determination TEXT NOT NULL,
            feedback_id TEXT, created_at TEXT NOT NULL);"""
    )
    old.execute(
        "INSERT INTO determinations VALUES ('d1', 'x', ?, NULL, 'now')",
        (json.dumps({"final": {"store": True, "memory_id": "m1"}}),),
    )
    old.execute("INSERT INTO determinations VALUES ('d2', 'y', '{\"final\": {}}', NULL, 'now')")
    old.commit()
    old.close()

    conn = init_db(db_path)

    rows = dict(conn.execute("SELECT id, memory_id FROM determinations").fetchall())
    assert rows == {"d1": "m1", "d2": None}
    indexes = [r[1] for r in conn.execute("PRAGMA index_list(determinations)")]
    assert "idx_determinations_memory" in indexes
    conn.close()

"""remember and recall with the keeper in front: no secret reaches a model, the log, or Chitta."""

from __future__ import annotations

import json

import pytest

from conftest import (
    FakeEmbeddings,
    FakeGemini,
    FakeTransport,
    determination_rows,
    jev_answer,
    make_buddhi,
    make_jev,
)
from secret_samples import a_secret_sentence, positives
from src.chitta.models import MemoryRecord
from src.chitta.schema import init_db
from src.chitta.store import ChittaStore
from src.dvarapala.keeper import SecretInWrite, default_keeper
from src.manas import tools

SAMPLE = a_secret_sentence()
SECRET = SAMPLE.values[0]


class SpyGemini(FakeGemini):
    """Records the content of every Gemini call."""

    def __init__(self, store: bool, **kwargs):
        super().__init__(store, **kwargs)
        self.contents: list[str] = []

    def _generate(self, **kwargs):
        self.contents.append(kwargs["contents"])
        return super()._generate(**kwargs)


class SpyEmbeddings(FakeEmbeddings):
    def __init__(self):
        self.texts: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.texts.append(text)
        return super().embed(text)


class BrokenKeeper:
    def scrub(self, _text):
        raise RuntimeError("rules unavailable")


def _remember(chitta, content, *, gemini=None, transport=None, **kwargs):
    gemini = gemini or SpyGemini(store=True)
    transport = transport or FakeTransport(jev_answer("decision"))
    embeddings = SpyEmbeddings()
    result = tools.remember(
        content,
        chitta=chitta,
        buddhi=make_buddhi(gemini, make_jev(transport)),
        embeddings=embeddings,
        **kwargs,
    )
    return result, gemini, transport, embeddings


def _everything_sent(gemini, transport, embeddings) -> str:
    return json.dumps(
        [gemini.contents, [c["body"] for c in transport.calls], embeddings.texts]
    )


def test_a_secret_is_scrubbed_before_every_model_call_and_every_write(chitta):
    result, gemini, transport, embeddings = _remember(chitta, SAMPLE.text, source_agent="pytest")

    assert result["stored"] is True
    assert result["redactions"] == [{"field": "content", "kind": "stripe-access-token", "count": 1}]
    assert "not stored" in result["note"]
    assert SECRET not in json.dumps(result)

    # Gemini, Jev and the embedder saw the scrubbed text, and only that
    scrubbed = SAMPLE.text.replace(SECRET, "[secret:stripe-access-token]")
    assert gemini.contents == [scrubbed]
    assert transport.calls[0]["body"]["state"]["memory"] == scrubbed
    assert embeddings.texts == [scrubbed]
    assert SECRET not in _everything_sent(gemini, transport, embeddings)

    # Chitta stored the scrubbed text, and the log row holds no trace of the value
    (record,) = chitta.stored
    assert record.content == scrubbed
    (row,) = determination_rows(chitta)
    assert row["input_text"] == scrubbed
    assert row["redactions"] == result["redactions"]
    assert SECRET not in json.dumps(row)


def test_nothing_but_a_secret_is_refused_without_any_model_call(chitta):
    bare = next(s for s in positives() if s.label == "stripe").values[0]

    result, gemini, transport, embeddings = _remember(chitta, f"STRIPE_KEY={bare}")

    assert result["stored"] is False
    assert result["reason"] == "secret_only"
    assert bare not in json.dumps(result)
    assert gemini.contents == [] and transport.calls == [] and embeddings.texts == []
    assert chitta.stored == []
    (row,) = determination_rows(chitta)
    assert row["decided_by"] == "dvarapala"
    assert row["final"] == {"store": False, "reason": "secret_only"}
    assert bare not in json.dumps(row)


def test_a_refused_memory_is_logged_scrubbed(chitta):
    result, gemini, _, _ = _remember(chitta, SAMPLE.text, gemini=SpyGemini(store=False))

    assert result["stored"] is False
    assert result["redactions"]
    (row,) = determination_rows(chitta)
    assert SECRET not in json.dumps(row)
    assert gemini.contents and SECRET not in gemini.contents[0]


def test_a_secret_in_the_scope_or_agent_override_is_dropped(chitta):
    result, gemini, _, _ = _remember(
        chitta,
        "We chose PostgreSQL for Jozu because of JSONB support.",
        scope=f"/project/{SECRET}",
        source_agent=SECRET,
    )

    (record,) = chitta.stored
    assert record.scope == gemini.answer["scope"]
    assert record.source_agent is None
    assert {r["field"] for r in result["redactions"]} == {"scope", "source_agent"}
    assert SECRET not in json.dumps(result)
    assert SECRET not in json.dumps(determination_rows(chitta))


def test_a_secret_echoed_by_buddhi_is_not_stored(chitta):
    gemini = SpyGemini(store=True)
    gemini.answer["scope"] = f"/project/stripe/{SECRET}"
    gemini.answer["categories"] = ["decision", SECRET]

    result, _, _, _ = _remember(chitta, "We moved FF payments to Stripe Checkout in 2026.",
                                gemini=gemini)

    (record,) = chitta.stored
    assert record.scope == "/"
    assert record.categories == ["decision"]
    assert SECRET not in json.dumps(result)
    # the log keeps Gemini's raw answer, scrubbed
    (row,) = determination_rows(chitta)
    assert SECRET not in json.dumps(row)
    assert "[secret:" in row["gemini"]["response"]["scope"]


def test_remember_fails_closed_when_the_keeper_fails(chitta):
    gemini, embeddings = SpyGemini(store=True), SpyEmbeddings()
    transport = FakeTransport(jev_answer("decision"))

    result = tools.remember(
        SAMPLE.text,
        chitta=chitta,
        buddhi=make_buddhi(gemini, make_jev(transport)),
        embeddings=embeddings,
        keeper=BrokenKeeper(),
    )

    assert result["stored"] is False
    assert result["reason"] == "keeper_error"
    assert gemini.contents == [] and transport.calls == [] and embeddings.texts == []
    assert chitta.stored == [] and determination_rows(chitta) == []


def test_recall_scrubs_the_query_before_embedding_it(chitta, monkeypatch):
    monkeypatch.setattr(chitta, "search", lambda **_kwargs: [])
    embeddings = SpyEmbeddings()

    result = tools.recall(f"which key is {SECRET}?", chitta=chitta, embeddings=embeddings)

    (embedded,) = embeddings.texts
    assert SECRET not in embedded
    assert embedded.startswith("which key is [secret:")
    assert result["query"] == embedded
    assert result["redactions"] == [{"field": "query", "kind": "high-entropy", "count": 1}]
    assert SECRET not in json.dumps(result)


def test_recall_without_a_secret_is_unchanged(chitta, monkeypatch):
    monkeypatch.setattr(chitta, "search", lambda **_kwargs: [])

    result = tools.recall("postgres decision", chitta=chitta, embeddings=SpyEmbeddings())

    assert result == {"query": "postgres decision", "count": 0, "memories": []}


def test_recall_fails_closed_when_the_keeper_fails(chitta):
    embeddings = SpyEmbeddings()

    result = tools.recall(SECRET, chitta=chitta, embeddings=embeddings, keeper=BrokenKeeper())

    assert result["error"] == "keeper_error"
    assert embeddings.texts == []
    assert SECRET not in json.dumps(result)


@pytest.fixture
def bare_chitta(tmp_path):
    """A ChittaStore with SQLite only: enough for the guards, which run before any write."""
    store = ChittaStore(tmp_path)
    store._db = init_db(tmp_path / "chitta.db")
    yield store
    store.close()


def test_chitta_refuses_to_store_a_secret(bare_chitta):
    with pytest.raises(SecretInWrite):
        bare_chitta.store(MemoryRecord(content=SAMPLE.text), [0.0] * 768)
    with pytest.raises(SecretInWrite):
        bare_chitta.store(MemoryRecord(content="clean", categories=[SECRET]), [0.0] * 768)

    assert bare_chitta._db.execute("SELECT COUNT(*) FROM memories").fetchone()[0] == 0


def test_chitta_refuses_to_log_a_secret(bare_chitta):
    with pytest.raises(SecretInWrite):
        bare_chitta.log_determination("clean", {"gemini": {"response": {"scope": SECRET}}})

    assert bare_chitta._db.execute("SELECT COUNT(*) FROM determinations").fetchone()[0] == 0


def test_no_data_file_holds_the_secret_after_remember(tmp_path):
    store = ChittaStore(tmp_path / "data")
    store.init()
    try:
        result, _, _, _ = _remember(store, SAMPLE.text)
        assert result["stored"] is True
    finally:
        store.close()

    files = [p for p in (tmp_path / "data").rglob("*") if p.is_file()]
    assert files
    assert not [p for p in files if SECRET.encode() in p.read_bytes()]


def test_the_default_keeper_is_shared():
    assert default_keeper() is default_keeper()

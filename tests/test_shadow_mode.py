"""Shadow mode: Jev's answer is logged, Buddhi's `store` decides, and Jev never blocks remember."""

from __future__ import annotations

import time

import pytest

from conftest import (
    FakeEmbeddings,
    FakeOpenRouter,
    FakeTransport,
    determination_rows,
    jev_answer,
    load_examples,
    make_buddhi,
    make_jev,
    opposite_kind,
)
from src.buddhi.jev import JevClient
from src.manas import tools

EXAMPLES = load_examples()


def _jev(behaviour: str, example: dict) -> JevClient | None:
    """A Jev client that agrees, disagrees, errors, or is too slow; None means off."""
    if behaviour == "off":
        return None
    if behaviour == "agrees":
        return make_jev(FakeTransport(jev_answer(example["kind"])))
    if behaviour == "disagrees":
        return make_jev(FakeTransport(jev_answer(opposite_kind(example["store"]))))
    if behaviour == "errors":
        return make_jev(FakeTransport({"error": "overloaded"}, status=529))
    if behaviour == "times-out":
        return make_jev(FakeTransport(jev_answer(example["kind"]), delay=1.0), timeout=0.1)
    raise AssertionError(behaviour)


EXPECTED_STATUS = {"off": "off", "agrees": "ok", "disagrees": "ok", "errors": "error", "times-out": "timeout"}


@pytest.mark.parametrize("behaviour", list(EXPECTED_STATUS))
@pytest.mark.parametrize("example", EXAMPLES, ids=lambda ex: ex["content"][:40])
def test_shadow_mode_does_not_change_the_stored_outcome(chitta, example, behaviour):
    model = FakeOpenRouter(store=example["store"])
    jev = _jev(behaviour, example)

    result = tools.remember(
        example["content"],
        chitta=chitta,
        buddhi=make_buddhi(model, jev),
        embeddings=FakeEmbeddings(),
        source_agent="pytest",
    )

    # Buddhi's answer alone decides, whatever Jev said
    assert result["stored"] is example["store"]
    assert len(chitta.stored) == (1 if example["store"] else 0)
    if example["store"]:
        assert result["scope"] == model.answer["scope"]
        assert result["categories"] == model.answer["categories"]
    else:
        assert result["reason"] == "Buddhi determined this content is too trivial to store."

    # ...and the determination, with both answers, is logged
    (row,) = determination_rows(chitta)
    if example["store"] or behaviour in ("agrees", "disagrees"):
        assert row["input_text"] == example["content"]
    else:
        assert row["input_text"] == "[redacted: likely secret]"
    assert row["decided_by"] == "buddhi"
    assert row["source_agent"] == "pytest"
    assert row["buddhi"]["model"] == "deepseek/deepseek-v4.1-flash"
    assert row["buddhi"]["response"] == model.answer
    assert row["final"]["store"] is example["store"]
    if example["store"]:
        assert row["final"]["memory_id"] == result["memory_id"]
    assert row["jev"]["status"] == EXPECTED_STATUS[behaviour]
    if behaviour != "off":
        assert row["jev"]["model_requested"] == "jev-1.13.0"
    if behaviour in ("agrees", "disagrees"):
        assert row["jev"]["model"] == "jev-1.13.0"
        assert row["jev"]["store"] is (example["store"] if behaviour == "agrees" else not example["store"])
        assert set(row["jev"]["kind_probabilities"]) == {
            "decision", "preference", "failed_approach", "durable_fact", "process", "transient"
        }


def test_a_refused_likely_secret_is_logged_without_its_text(chitta):
    secret = "The prod API key is sk-live-4f9a2b7c1d8e"
    model = FakeOpenRouter(store=False)

    result = tools.remember(
        secret,
        chitta=chitta,
        buddhi=make_buddhi(model, make_jev(FakeTransport(jev_answer("durable_fact", secret=0.97)))),
        embeddings=FakeEmbeddings(),
        source_agent="pytest",
    )

    assert result["stored"] is False
    assert chitta.stored == []
    (row,) = determination_rows(chitta)
    assert row["input_text"] == "[redacted: likely secret]"
    assert row["final"] == {"store": False}
    assert row["buddhi"]["model"] == "deepseek/deepseek-v4.1-flash"
    assert row["buddhi"]["response"] == model.answer
    assert row["jev"]["model"] == "jev-1.13.0"
    assert row["jev"]["secret_probability"] == 0.97
    assert row["jev"]["store"] is False
    raw_rows = chitta._db.execute("SELECT * FROM determinations").fetchall()
    assert all("sk-live-4f9a2b7c1d8e" not in str(value) for r in raw_rows for value in tuple(r))


@pytest.mark.parametrize("behaviour", ["off", "errors", "times-out"])
def test_a_refused_input_without_a_jev_answer_is_logged_without_its_text(chitta, behaviour):
    secret = "The prod API key is sk-live-4f9a2b7c1d8e"
    model = FakeOpenRouter(store=False)

    result = tools.remember(
        secret,
        chitta=chitta,
        buddhi=make_buddhi(model, _jev(behaviour, {"kind": "durable_fact", "store": False})),
        embeddings=FakeEmbeddings(),
        source_agent="pytest",
    )

    assert result["stored"] is False
    (row,) = determination_rows(chitta)
    assert row["input_text"] == "[redacted: likely secret]"
    assert row["final"] == {"store": False}
    assert row["buddhi"]["response"] == model.answer
    assert row["jev"]["status"] == EXPECTED_STATUS[behaviour]
    raw_rows = chitta._db.execute("SELECT * FROM determinations").fetchall()
    assert all("sk-live-4f9a2b7c1d8e" not in str(value) for r in raw_rows for value in tuple(r))


def test_overrides_apply_and_are_logged_as_the_final_decision(chitta):
    tools.remember(
        "We chose PostgreSQL because JSONB support.",
        chitta=chitta,
        buddhi=make_buddhi(FakeOpenRouter(store=True), make_jev(FakeTransport(jev_answer("process")))),
        embeddings=FakeEmbeddings(),
        scope="/project/override",
        importance=0.3,
    )

    (row,) = determination_rows(chitta)
    assert row["final"]["scope"] == "/project/override"
    assert row["final"]["importance"] == 0.3
    assert row["buddhi"]["response"]["scope"] == "/project/test"


def test_slow_jev_adds_no_more_than_its_timeout():
    buddhi = make_buddhi(
        FakeOpenRouter(store=True),
        make_jev(FakeTransport(jev_answer("decision"), delay=2.0), timeout=0.2),
    )

    started = time.monotonic()
    determination = buddhi.evaluate("We chose PostgreSQL because JSONB support.")
    elapsed = time.monotonic() - started

    assert determination.store is True
    assert determination.trace["jev"]["status"] == "timeout"
    assert elapsed < 0.6


def test_jev_timeout_is_counted_from_the_start_so_a_slow_buddhi_absorbs_it():
    buddhi = make_buddhi(
        FakeOpenRouter(store=True, delay=0.4),
        make_jev(FakeTransport(jev_answer("decision"), delay=2.0), timeout=0.2),
    )

    started = time.monotonic()
    buddhi.evaluate("We chose PostgreSQL because JSONB support.")
    elapsed = time.monotonic() - started

    assert elapsed < 0.4 + 0.15  # Buddhi's time, with no Jev wait on top


def test_jev_runs_alongside_buddhi():
    buddhi = make_buddhi(
        FakeOpenRouter(store=True, delay=0.3),
        make_jev(FakeTransport(jev_answer("decision"), delay=0.3), timeout=1.0),
    )

    started = time.monotonic()
    determination = buddhi.evaluate("We chose PostgreSQL because JSONB support.")
    elapsed = time.monotonic() - started

    assert determination.trace["jev"]["status"] == "ok"
    assert elapsed < 0.3 + 0.2  # parallel, not 0.6 in sequence


def test_unexpected_jev_exception_falls_back(chitta, monkeypatch):
    jev = make_jev(FakeTransport(jev_answer("decision")))
    monkeypatch.setattr(jev, "judge", lambda _content: 1 / 0)

    result = tools.remember(
        "We chose PostgreSQL because JSONB support.",
        chitta=chitta,
        buddhi=make_buddhi(FakeOpenRouter(store=True), jev),
        embeddings=FakeEmbeddings(),
    )

    assert result["stored"] is True
    (row,) = determination_rows(chitta)
    assert row["jev"]["status"] == "error"


def test_a_logging_failure_does_not_block_remember(chitta, monkeypatch):
    def broken_log(*_args):
        raise RuntimeError("disk full")

    monkeypatch.setattr(chitta, "log_determination", broken_log)

    result = tools.remember(
        "We chose PostgreSQL because JSONB support.",
        chitta=chitta,
        buddhi=make_buddhi(FakeOpenRouter(store=True)),
        embeddings=FakeEmbeddings(),
    )

    assert result["stored"] is True
    assert len(chitta.stored) == 1


def test_a_failed_store_is_logged_and_still_raised(chitta, monkeypatch):
    def broken_store(_record, _embedding):
        raise RuntimeError("zvec write failed")

    monkeypatch.setattr(chitta, "store", broken_store)

    with pytest.raises(RuntimeError, match="zvec write failed"):
        tools.remember(
            "We chose PostgreSQL because JSONB support.",
            chitta=chitta,
            buddhi=make_buddhi(FakeOpenRouter(store=True)),
            embeddings=FakeEmbeddings(),
        )

    (row,) = determination_rows(chitta)
    assert row["final"] == {"store": False, "error": "RuntimeError: zvec write failed"}


def test_a_buddhi_failure_refuses_remember_and_logs_why(chitta):
    buddhi = make_buddhi(
        FakeOpenRouter(store=True, error=RuntimeError("model down")),
        make_jev(FakeTransport(jev_answer("decision"))),
    )

    result = tools.remember(
        "We chose PostgreSQL because JSONB support.",
        chitta=chitta,
        buddhi=buddhi,
        embeddings=FakeEmbeddings(),
        source_agent="pytest",
    )

    assert result["stored"] is False
    assert result["reason"] == "buddhi_error"
    assert "model down" in result["note"]
    assert chitta.stored == []
    (row,) = determination_rows(chitta)
    assert row["decided_by"] == "buddhi"
    assert row["buddhi"]["status"] == "error"
    assert "model down" in row["buddhi"]["error"]
    assert "response" not in row["buddhi"]
    assert row["final"] == {"store": False, "reason": "buddhi_error"}
    # Jev's shadow answer is still logged, and never stores anything on its own
    assert row["jev"]["status"] == "ok" and row["jev"]["store"] is True
    assert row["input_text"] == "We chose PostgreSQL because JSONB support."

"""JevClient: the request it sends and how it reads, or rejects, Jev's answer."""

from __future__ import annotations

import json
import os
import urllib.error

import pytest

from conftest import TEST_KEY, FakeTransport, jev_answer, load_examples, make_jev
from src.buddhi.jev import JEV_MODEL, JEV_TIMEOUT_S, KEEP_KINDS, JevClient, JevError


def test_request_is_pinned_and_carries_only_the_memory():
    transport = FakeTransport(jev_answer("decision"))
    JevClient(TEST_KEY, transport=transport).judge("We chose PostgreSQL because JSONB support.")

    (call,) = transport.calls
    assert call["url"] == "https://api.typesafe.ai/v1/systemone"
    assert call["body"]["model"] == JEV_MODEL == "jev-1.13.0"
    assert call["body"]["state"] == {"memory": "We chose PostgreSQL because JSONB support."}
    assert set(call["body"]["questions"]) == {"kind", "secret"}
    assert call["headers"]["Authorization"] == f"Bearer {TEST_KEY}"
    assert call["timeout"] == JEV_TIMEOUT_S


@pytest.mark.parametrize(
    ("kind", "secret", "store"),
    [
        ("decision", 0.02, True),
        ("preference", 0.02, True),
        ("failed_approach", 0.02, True),
        ("durable_fact", 0.02, True),
        ("process", 0.02, False),
        ("transient", 0.02, False),
        ("durable_fact", 0.9, False),  # a secret is refused whatever its kind
    ],
)
def test_keep_probability_and_store(kind, secret, store):
    judgment = make_jev(FakeTransport(jev_answer(kind, secret=secret))).judge("memory")

    assert judgment.kind == kind
    assert judgment.model == "jev-1.13.0"
    assert judgment.secret_probability == secret
    # jev_answer puts 0.9 on `kind` and spreads 0.1 evenly over the other five
    other_keep_kinds = len([k for k in KEEP_KINDS if k != kind])
    expected_keep = (0.9 if kind in KEEP_KINDS else 0.0) + 0.02 * other_keep_kinds
    assert judgment.store_probability == pytest.approx(expected_keep)
    assert judgment.store is store


def test_rounded_probabilities_off_1_are_renormalized():
    answer = jev_answer("decision")
    answer["answers"]["kind"]["probabilities"] = {
        "decision": 0.33,
        "preference": 0.33,
        "durable_fact": 0.12,
        "failed_approach": 0.12,
        "process": 0.06,
        "transient": 0.06,
    }  # sums to 1.02

    judgment = make_jev(FakeTransport(answer)).judge("memory")

    assert judgment.store_probability == pytest.approx(0.90 / 1.02)
    assert judgment.store is True


def _broken(mutate):
    answer = jev_answer("decision")
    mutate(answer)
    return answer


@pytest.mark.parametrize(
    "transport",
    [
        FakeTransport({"error": "overloaded"}, status=529),
        FakeTransport({"error": "bad key"}, status=401),
        FakeTransport(b"not json"),
        FakeTransport({"model": "jev-1.13.0"}),
        FakeTransport(_broken(lambda a: a["answers"].pop("secret"))),
        FakeTransport(_broken(lambda a: a["answers"]["kind"]["probabilities"].pop("process"))),
        FakeTransport(_broken(lambda a: a["answers"]["kind"]["probabilities"].update(
            dict.fromkeys(a["answers"]["kind"]["probabilities"], 0.0)
        ))),
        FakeTransport(_broken(lambda a: a["answers"]["kind"].update(choice="summary"))),
        FakeTransport(_broken(lambda a: a["answers"]["secret"].update(noul="high"))),
        FakeTransport(_broken(lambda a: a["answers"]["kind"].update(confidence=None))),
        FakeTransport(error=TimeoutError("timed out")),
        FakeTransport(error=urllib.error.URLError("name resolution failed")),
    ],
    ids=[
        "http-529",
        "http-401",
        "not-json",
        "no-answers",
        "no-secret-answer",
        "missing-kind",
        "all-zero-probabilities",
        "unknown-choice",
        "non-numeric-noul",
        "no-confidence",
        "socket-timeout",
        "network-error",
    ],
)
def test_every_failure_is_a_jev_error_without_the_key(transport):
    with pytest.raises(JevError) as caught:
        make_jev(transport).judge("memory")
    assert TEST_KEY not in str(caught.value)


@pytest.mark.skipif(not os.environ.get("TYPESAFE_API_KEY"), reason="live Jev check needs TYPESAFE_API_KEY")
@pytest.mark.parametrize("example", load_examples(), ids=lambda ex: ex["content"][:40])
def test_live_jev_on_fixture_examples(example):
    """Opt-in check against the real API: Jev should agree with each fixture label."""
    judgment = JevClient(os.environ["TYPESAFE_API_KEY"]).judge(example["content"])
    assert judgment.store is example["store"], json.dumps(judgment.to_dict())

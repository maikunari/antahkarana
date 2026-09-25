"""BuddhiEngine: the OpenRouter request it sends and how it reads, or refuses, the answer."""

from __future__ import annotations

import json
import os
import socket
import urllib.error

import pytest

from conftest import CONFIG_DIR, TEST_KEY, FakeOpenRouter, load_examples, make_buddhi
from src.buddhi.engine import (
    BUDDHI_MODEL_ENV,
    BUDDHI_TIMEOUT_S,
    DEFAULT_BUDDHI_MODEL,
    BuddhiEngine,
    buddhi_model,
)


def test_request_asks_openrouter_for_strict_json():
    model = FakeOpenRouter(store=True)
    make_buddhi(model).evaluate("We chose PostgreSQL because JSONB support.")

    (call,) = model.calls
    body = call["body"]
    assert call["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert call["headers"]["Authorization"] == f"Bearer {TEST_KEY}"
    assert call["timeout"] == BUDDHI_TIMEOUT_S
    assert body["model"] == DEFAULT_BUDDHI_MODEL == "deepseek/deepseek-v4.1-flash"
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][0]["content"].startswith("You are Buddhi")
    assert body["messages"][1] == {
        "role": "user",
        "content": "We chose PostgreSQL because JSONB support.",
    }
    schema = body["response_format"]["json_schema"]
    assert body["response_format"]["type"] == "json_schema" and schema["strict"] is True
    assert set(schema["schema"]["required"]) == {"store", "importance", "scope", "categories"}
    assert schema["schema"]["additionalProperties"] is False
    assert body["provider"] == {"require_parameters": True}


def test_model_comes_from_the_environment(monkeypatch):
    monkeypatch.delenv(BUDDHI_MODEL_ENV, raising=False)
    assert buddhi_model() == DEFAULT_BUDDHI_MODEL
    monkeypatch.setenv(BUDDHI_MODEL_ENV, "  ")
    assert buddhi_model() == DEFAULT_BUDDHI_MODEL
    monkeypatch.setenv(BUDDHI_MODEL_ENV, "qwen/qwen3-next")

    model = FakeOpenRouter(store=True)
    buddhi = BuddhiEngine(TEST_KEY, str(CONFIG_DIR), transport=model)
    determination = buddhi.evaluate("We chose PostgreSQL because JSONB support.")

    assert model.calls[0]["body"]["model"] == "qwen/qwen3-next"
    assert determination.trace["buddhi"]["model"] == "qwen/qwen3-next"


def test_a_well_formed_answer_decides_and_is_traced():
    model = FakeOpenRouter(store=True)
    determination = make_buddhi(model).evaluate("We chose PostgreSQL because JSONB support.")

    assert determination.store is True
    assert determination.error is None
    assert determination.importance == 0.8
    assert determination.scope == "/project/test"
    assert determination.categories == ["decision"]
    trace = determination.trace
    assert trace["decided_by"] == "buddhi"
    assert trace["buddhi"]["provider"] == "openrouter"
    assert trace["buddhi"]["status"] == "ok"
    assert trace["buddhi"]["model"] == "deepseek/deepseek-v4.1-flash"
    assert trace["buddhi"]["model_version"] == "deepseek/deepseek-v4.1-flash-20260910"
    assert trace["buddhi"]["served_by"] == "TestProvider"
    assert trace["buddhi"]["response"] == model.answer
    assert trace["jev"] == {"status": "off"}


def _answer(**fields) -> str:
    base = {"store": True, "importance": 0.8, "scope": "/p", "categories": ["decision"]}
    return json.dumps({**base, **fields})


MALFORMED_ANSWERS = {
    "prose": "Sure! Here is the JSON: {}",
    "fenced": "```json\n" + _answer() + "\n```",
    "array": "[]",
    "missing-field": json.dumps({"store": True, "importance": 0.8, "scope": "/p"}),
    "extra-field": _answer(summary="extra"),
    "store-string": _answer(store="true"),
    "importance-string": _answer(importance="0.8"),
    "importance-bool": _answer(importance=True),
    "importance-above-1": _answer(importance=1.5),
    "importance-negative": _answer(importance=-0.1),
    "scope-not-a-path": _answer(scope="project/x"),
    "scope-null": _answer(scope=None),
    "categories-string": _answer(categories="decision"),
    "categories-mixed": _answer(categories=["decision", 3]),
}


@pytest.mark.parametrize("raw", MALFORMED_ANSWERS.values(), ids=MALFORMED_ANSWERS.keys())
def test_a_malformed_answer_is_a_refusal(raw):
    model = FakeOpenRouter(store=True)
    model.raw = raw

    determination = make_buddhi(model).evaluate("We chose PostgreSQL because JSONB support.")

    assert determination.store is False
    assert determination.error
    assert determination.trace["buddhi"]["status"] == "error"
    assert determination.trace["buddhi"]["error"] == determination.error
    assert "response" not in determination.trace["buddhi"]


def _response(content: object, finish_reason: object = "stop") -> dict:
    return {"choices": [{"finish_reason": finish_reason, "message": {"content": content}}]}


BAD_RESPONSES = {
    "http-401": (FakeOpenRouter(store=True, status=401), None, "http 401"),
    "http-429": (FakeOpenRouter(store=True, status=429), None, "http 429"),
    "not-json": (FakeOpenRouter(store=True), b"<html>bad gateway</html>", "not JSON"),
    "no-choices": (FakeOpenRouter(store=True), {"choices": []}, "no choices"),
    "provider-error": (
        FakeOpenRouter(store=True),
        {"error": {"code": 502, "message": "upstream failed"}},
        "provider error",
    ),
    "truncated": (FakeOpenRouter(store=True), _response(_answer(), "length"), "did not finish"),
    "null-content": (FakeOpenRouter(store=True), _response(None), "no text content"),
    "timeout": (FakeOpenRouter(store=True, error=socket.timeout("timed out")), None, "timed out"),
    "network": (
        FakeOpenRouter(store=True, error=urllib.error.URLError("no route")),
        None,
        "no route",
    ),
}


@pytest.mark.parametrize(("model", "response", "error"), BAD_RESPONSES.values(), ids=BAD_RESPONSES.keys())
def test_every_failure_is_a_refusal_without_the_key(model, response, error):
    model.response = response

    determination = make_buddhi(model).evaluate("memory")

    assert determination.store is False
    assert error in determination.error
    assert TEST_KEY not in determination.error


@pytest.mark.skipif(
    not os.environ.get("OPENROUTER_API_KEY"), reason="live Buddhi check needs OPENROUTER_API_KEY"
)
@pytest.mark.parametrize("example", load_examples(), ids=lambda ex: ex["content"][:40])
def test_live_buddhi_on_fixture_examples(example):
    """Opt-in check against the real API: the model answers strictly and agrees with each label."""
    buddhi = BuddhiEngine(os.environ["OPENROUTER_API_KEY"], str(CONFIG_DIR))
    determination = buddhi.evaluate(example["content"])
    assert determination.error is None, determination.error
    assert determination.store is example["store"], json.dumps(determination.trace)

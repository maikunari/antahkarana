"""Shared fakes: OpenRouter and Jev transports, embeddings, and a SQLite-only Chitta."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
import yaml

from src.buddhi.engine import DEFAULT_BUDDHI_MODEL, BuddhiEngine
from src.buddhi.jev import KEEP_KINDS, KIND_CRITERIA, JevClient
from src.chitta.schema import init_db
from src.chitta.store import ChittaStore

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
TEST_KEY = "test-key-never-printed"


def load_examples() -> list[dict]:
    """Every fixture example, with `store` set from the list it sits in."""
    with open(Path(__file__).parent / "fixtures" / "buddhi_examples.yaml") as f:
        data = yaml.safe_load(f)
    return [{**ex, "store": True} for ex in data["kept"]] + [
        {**ex, "store": False} for ex in data["refused"]
    ]


class FakeOpenRouter:
    """Stands in for the OpenRouter transport; answers every call with one fixed determination.

    `answer` is the determination JSON; `raw` overrides the whole message content
    and `response` the whole response body, for malformed-output tests.
    """

    def __init__(
        self,
        store: bool,
        *,
        delay: float = 0.0,
        error: Exception | None = None,
        status: int = 200,
    ):
        self.answer = {
            "store": store,
            "importance": 0.8 if store else 0.1,
            "scope": "/project/test",
            "categories": ["decision"] if store else [],
        }
        self.delay = delay
        self.error = error
        self.status = status
        self.raw: str | None = None
        self.response: object | None = None
        self.calls: list[dict] = []

    @property
    def contents(self) -> list[str]:
        """The user message of every call: the text the model saw."""
        return [c["body"]["messages"][-1]["content"] for c in self.calls]

    def __call__(self, url, body, headers, timeout):
        self.calls.append(
            {"url": url, "body": json.loads(body), "headers": headers, "timeout": timeout}
        )
        time.sleep(self.delay)
        if self.error:
            raise self.error
        if self.response is not None:
            body = self.response
        else:
            content = self.raw if self.raw is not None else json.dumps(self.answer)
            body = {
                "id": "gen-test",
                "model": "deepseek/deepseek-v4.1-flash-20260910",
                "provider": "TestProvider",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": content},
                    }
                ],
            }
        return self.status, body if isinstance(body, bytes) else json.dumps(body).encode()


def jev_answer(kind: str, *, secret: float = 0.02, model: str = "jev-1.13.0") -> dict:
    """A well-formed Jev response that puts 0.9 on `kind`."""
    others = [k for k in KIND_CRITERIA if k != kind]
    probabilities = {k: 0.1 / len(others) for k in others}
    probabilities[kind] = 0.9
    return {
        "model": model,
        "answers": {
            "kind": {
                "type": "choice",
                "choice": kind,
                "probabilities": probabilities,
                "confidence": 0.8,
            },
            "secret": {"type": "noul", "noul": secret},
        },
        "usage": {"input_tokens": 300, "output_tokens": 20},
    }


def opposite_kind(store: bool) -> str:
    return "process" if store else KEEP_KINDS[0]


class FakeTransport:
    """Records each Jev request and returns a canned response, or raises, after an optional delay."""

    def __init__(self, response=None, *, status: int = 200, delay: float = 0.0, error=None):
        self.body = response if isinstance(response, bytes) else json.dumps(response).encode()
        self.status = status
        self.delay = delay
        self.error = error
        self.calls: list[dict] = []

    def __call__(self, url, body, headers, timeout):
        self.calls.append(
            {"url": url, "body": json.loads(body), "headers": headers, "timeout": timeout}
        )
        time.sleep(self.delay)
        if self.error:
            raise self.error
        return self.status, self.body


def make_jev(transport: FakeTransport, *, timeout: float = 1.0) -> JevClient:
    return JevClient(TEST_KEY, timeout=timeout, transport=transport)


def make_buddhi(model: FakeOpenRouter, jev: JevClient | None = None) -> BuddhiEngine:
    return BuddhiEngine(
        api_key=TEST_KEY,
        config_dir=str(CONFIG_DIR),
        model=DEFAULT_BUDDHI_MODEL,
        jev=jev,
        transport=model,
    )


class FakeEmbeddings:
    def embed(self, _text: str) -> list[float]:
        return [0.0] * 768

    def embed_query(self, _text: str) -> list[float]:
        return [0.0] * 768


@pytest.fixture
def chitta(tmp_path, monkeypatch) -> ChittaStore:
    """A ChittaStore on real SQLite; the Zvec write is replaced by a recorder."""
    store = ChittaStore(tmp_path)
    store._db = init_db(tmp_path / "chitta.db")
    store.stored = []
    monkeypatch.setattr(store, "store", lambda record, _embedding: store.stored.append(record))
    yield store
    store.close()


def determination_rows(chitta: ChittaStore) -> list[dict]:
    rows = chitta._db.execute(
        "SELECT input_text, determination FROM determinations ORDER BY created_at"
    ).fetchall()
    return [{"input_text": r["input_text"], **json.loads(r["determination"])} for r in rows]

"""EmbeddingEngine: task prefixes, unit vectors, and the pinned local model."""

from __future__ import annotations

import os

import numpy as np
import pytest

from src.buddhi.embeddings import (
    DOCUMENT_PREFIX,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    EMBEDDING_REVISION,
    QUERY_PREFIX,
    EmbeddingEngine,
)
from src.chitta.store import EMBEDDING_DIM


class FakeModel:
    """Stands in for fastembed's TextEmbedding; records what it was asked to embed."""

    def __init__(self):
        self.texts: list[str] = []

    def embed(self, texts):
        self.texts.extend(texts)
        return [np.full(EMBEDDING_DIMENSIONS, 3.0, dtype=np.float32) for _ in texts]


@pytest.fixture
def engine(monkeypatch):
    engine = EmbeddingEngine()
    engine.fake = FakeModel()
    monkeypatch.setattr(engine, "load", lambda: engine.fake)
    return engine


def test_model_is_pinned_and_matches_the_vector_store():
    assert EMBEDDING_MODEL == "nomic-ai/nomic-embed-text-v1.5"
    assert len(EMBEDDING_REVISION) == 40  # a commit hash, not a moving branch
    assert EMBEDDING_DIMENSIONS == EMBEDDING_DIM == 768


def test_stored_text_and_queries_get_their_task_prefixes(engine):
    engine.embed("We chose Postgres.")
    engine.embed_query("which database?")

    assert engine.fake.texts == [DOCUMENT_PREFIX + "We chose Postgres.", QUERY_PREFIX + "which database?"]


def test_vectors_are_unit_length(engine):
    vector = engine.embed("We chose Postgres.")

    assert len(vector) == 768
    assert np.linalg.norm(vector) == pytest.approx(1.0)


def test_the_model_is_not_loaded_until_first_use():
    assert EmbeddingEngine()._model is None


@pytest.mark.skipif(
    not os.environ.get("ANTAHKARANA_LIVE_EMBEDDINGS"),
    reason="live embedding check downloads the model; set ANTAHKARANA_LIVE_EMBEDDINGS=1",
)
def test_live_model_ranks_the_relevant_memory_first():
    engine = EmbeddingEngine()
    memories = [
        "We chose PostgreSQL for Jozu because of JSONB support.",
        "Mike prefers short replies in Discord.",
    ]
    vectors = [engine.embed(m) for m in memories]
    query = engine.embed_query("which database did we pick?")

    assert len(query) == 768
    scores = [float(np.dot(query, v)) for v in vectors]
    assert scores[0] > scores[1]

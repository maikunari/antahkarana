"""Local embedding model for text → vector conversion.

Runs on this machine through ONNX Runtime (fastembed): it needs no API key and
no memory text leaves the machine. The model files are fetched once, at the
pinned revision, into the Hugging Face cache on first use.
"""

from __future__ import annotations

import threading

import numpy as np

EMBEDDING_MODEL = "nomic-ai/nomic-embed-text-v1.5"
# Pinned: the Hugging Face revision the model files are fetched at.
EMBEDDING_REVISION = "e9b6763023c676ca8431644204f50c2b100d9aab"
EMBEDDING_DIMENSIONS = 768
_MODEL_FILES = [
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "onnx/model.onnx",
]

# nomic-embed-text is trained with task prefixes: stored text and search queries differ.
DOCUMENT_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "


class EmbeddingEngine:
    """Wraps the pinned local embedding model. Loads it on first use."""

    def __init__(self) -> None:
        self._model = None
        self._lock = threading.Lock()

    def embed(self, text: str) -> list[float]:
        """Convert text to be stored into a 768-dimensional unit vector."""
        return self._embed(DOCUMENT_PREFIX + text)

    def embed_query(self, text: str) -> list[float]:
        """Convert a search query into a 768-dimensional unit vector."""
        return self._embed(QUERY_PREFIX + text)

    def _embed(self, text: str) -> list[float]:
        (vector,) = self.load().embed([text])
        norm = float(np.linalg.norm(vector))
        # Unit length, so Zvec's inner product is cosine similarity.
        return (vector / norm).tolist() if norm > 0 else vector.tolist()

    def load(self):
        """Fetch (first time only) and load the pinned model. Idempotent."""
        with self._lock:
            if self._model is None:
                from fastembed import TextEmbedding
                from huggingface_hub import snapshot_download

                path = snapshot_download(
                    EMBEDDING_MODEL,
                    revision=EMBEDDING_REVISION,
                    allow_patterns=_MODEL_FILES,
                )
                self._model = TextEmbedding(EMBEDDING_MODEL, specific_model_path=path)
            return self._model

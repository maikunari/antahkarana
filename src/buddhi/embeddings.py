"""Gemini embedding wrapper for text → vector conversion."""

from google import genai
from google.genai import types

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768


class EmbeddingEngine:
    """Wraps the Gemini embedding API."""

    def __init__(self, api_key: str) -> None:
        self._client = genai.Client(api_key=api_key)

    def embed(self, text: str) -> list[float]:
        """Convert text to a 768-dimensional embedding vector."""
        response = self._client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=EMBEDDING_DIMENSIONS,
            ),
        )
        return list(response.embeddings[0].values)

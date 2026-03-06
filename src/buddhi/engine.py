"""Buddhi — the determining faculty. Evaluates incoming content via Gemini Flash."""

from __future__ import annotations

import json
import logging

from google import genai
from google.genai import types
from pydantic import BaseModel

from src.buddhi.prompts import load_buddhi_prompt
from src.chitta.models import BuddhiDetermination

logger = logging.getLogger(__name__)

BUDDHI_MODEL = "gemini-2.5-flash"


class _DeterminationSchema(BaseModel):
    """Schema for structured JSON output from Gemini."""

    importance: float
    scope: str
    categories: list[str]
    store: bool


class BuddhiEngine:
    """The reasoning/inference layer that evaluates content for storage."""

    def __init__(self, api_key: str, config_dir: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._system_prompt = load_buddhi_prompt(config_dir)

    def evaluate(self, content: str) -> BuddhiDetermination:
        """Evaluate content and determine importance, scope, categories, and whether to store."""
        response = self._client.models.generate_content(
            model=BUDDHI_MODEL,
            contents=content,
            config=types.GenerateContentConfig(
                system_instruction=self._system_prompt,
                response_mime_type="application/json",
                response_schema=_DeterminationSchema,
                temperature=0.2,
            ),
        )

        data = json.loads(response.text)
        return BuddhiDetermination(
            importance=max(0.0, min(1.0, data["importance"])),
            scope=data.get("scope", "/"),
            categories=data.get("categories", []),
            store=data.get("store", True),
        )

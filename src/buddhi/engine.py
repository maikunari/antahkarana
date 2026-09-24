"""Buddhi — the determining faculty. Evaluates incoming content via Gemini Flash.

When a Jev client is configured, Jev judges the same content in shadow mode:
it runs alongside Gemini, its answer is recorded in the determination trace,
and Gemini's `store` still decides.
"""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor

from google import genai
from google.genai import types
from pydantic import BaseModel

from src.buddhi.jev import JevClient, JevJudgment
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

    def __init__(
        self,
        api_key: str,
        config_dir: str,
        *,
        jev: JevClient | None = None,
        gemini_client: genai.Client | None = None,
    ) -> None:
        self._client = gemini_client or genai.Client(api_key=api_key)
        self._system_prompt = load_buddhi_prompt(config_dir)
        self._jev = jev
        self._jev_pool = (
            ThreadPoolExecutor(max_workers=4, thread_name_prefix="jev-shadow")
            if jev is not None
            else None
        )

    def evaluate(self, content: str) -> BuddhiDetermination:
        """Evaluate content and determine importance, scope, categories, and whether to store."""
        started = time.monotonic()
        jev_future = self._start_jev(content)

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
            trace={
                "decided_by": "gemini",
                "gemini": {
                    "model": BUDDHI_MODEL,
                    "model_version": getattr(response, "model_version", None),
                    "response": data,
                },
                "jev": self._finish_jev(jev_future, started),
            },
        )

    def _start_jev(self, content: str) -> Future[JevJudgment] | None:
        if self._jev is None or self._jev_pool is None:
            return None
        try:
            return self._jev_pool.submit(self._jev.judge, content)
        except Exception:
            logger.warning("Jev shadow call could not start", exc_info=True)
            return None

    def _finish_jev(self, future: Future[JevJudgment] | None, started: float) -> dict:
        """Collect the shadow answer without waiting past Jev's timeout, counted from the start."""
        if self._jev is None:
            return {"status": "off"}
        shadow = {"model_requested": self._jev.model}
        if future is None:
            return {"status": "error", **shadow, "error": "call did not start"}
        remaining = max(0.0, started + self._jev.timeout - time.monotonic())
        try:
            judgment = future.result(timeout=remaining)
        except TimeoutError:
            future.cancel()
            return {"status": "timeout", **shadow, "error": f"no answer within {self._jev.timeout}s"}
        except Exception as err:
            logger.warning("Jev shadow call failed: %s", err)
            return {"status": "error", **shadow, "error": str(err)}
        return {"status": "ok", **shadow, **judgment.to_dict()}

"""Buddhi — the determining faculty. Evaluates incoming content via OpenRouter.

Buddhi asks an open model on OpenRouter's OpenAI-compatible chat completions
API for a strict JSON determination. Any failure (network, HTTP status,
timeout, or an answer that does not match the schema) becomes a refusal:
nothing is stored, and the error is recorded in the determination trace.

When a Jev client is configured, Jev judges the same content in shadow mode:
it runs alongside Buddhi's model, its answer is recorded in the determination
trace, and Buddhi's `store` still decides.
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
from concurrent.futures import Future, ThreadPoolExecutor

from src.buddhi.jev import JevClient, JevJudgment, Transport, urllib_transport
from src.buddhi.prompts import load_buddhi_prompt
from src.chitta.models import BuddhiDetermination

logger = logging.getLogger(__name__)

OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
BUDDHI_MODEL_ENV = "ANTAHKARANA_BUDDHI_MODEL"
# OpenRouter's id for DeepSeek V4.1 Flash.
DEFAULT_BUDDHI_MODEL = "deepseek/deepseek-v4.1-flash"
BUDDHI_TIMEOUT_S = 30.0

DETERMINATION_SCHEMA = {
    "type": "object",
    "properties": {
        "store": {"type": "boolean"},
        "importance": {"type": "number", "minimum": 0, "maximum": 1},
        "scope": {"type": "string"},
        "categories": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["store", "importance", "scope", "categories"],
    "additionalProperties": False,
}


class BuddhiError(Exception):
    """Any Buddhi model failure: network, HTTP status, timeout, or a malformed answer."""


def buddhi_model() -> str:
    """The OpenRouter model id Buddhi asks, from the environment or the default."""
    return os.environ.get(BUDDHI_MODEL_ENV, "").strip() or DEFAULT_BUDDHI_MODEL


def parse_determination(content: object) -> dict:
    """Parse the model's answer strictly. Raises BuddhiError unless it matches the schema."""
    if not isinstance(content, str):
        raise BuddhiError("answer has no text content")
    try:
        data = json.loads(content)
    except ValueError as err:
        raise BuddhiError("answer is not JSON") from err
    if not isinstance(data, dict):
        raise BuddhiError("answer is not a JSON object")
    if set(data) != set(DETERMINATION_SCHEMA["required"]):
        raise BuddhiError("answer fields are not exactly store, importance, scope, categories")

    importance = data["importance"]
    if isinstance(importance, bool) or not isinstance(importance, (int, float)):
        raise BuddhiError("importance is not a number")
    if not math.isfinite(importance) or not 0.0 <= importance <= 1.0:
        raise BuddhiError("importance is outside 0..1")
    if not isinstance(data["store"], bool):
        raise BuddhiError("store is not a boolean")
    scope = data["scope"]
    if not isinstance(scope, str):
        raise BuddhiError("scope is not a string")
    scope = scope.strip()
    if not scope.startswith("/"):
        scope = "/" + scope
    categories = data["categories"]
    if not isinstance(categories, list) or not all(isinstance(c, str) for c in categories):
        raise BuddhiError("categories is not a list of strings")
    return {**data, "importance": float(importance), "scope": scope}


class BuddhiEngine:
    """The reasoning/inference layer that evaluates content for storage."""

    def __init__(
        self,
        api_key: str,
        config_dir: str,
        *,
        model: str | None = None,
        jev: JevClient | None = None,
        transport: Transport | None = None,
    ) -> None:
        self._api_key = api_key
        self.model = model or buddhi_model()
        self._transport = transport or urllib_transport
        self._system_prompt = load_buddhi_prompt(config_dir)
        self._jev = jev
        self._jev_pool = (
            ThreadPoolExecutor(max_workers=4, thread_name_prefix="jev-shadow")
            if jev is not None
            else None
        )

    def request_body(self, content: str) -> dict:
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": content},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "buddhi_determination",
                    "strict": True,
                    "schema": DETERMINATION_SCHEMA,
                },
            },
            "temperature": 0.2,
            # A short classification: no reasoning tokens to wait for or pay for.
            "reasoning": {"enabled": False},
            # Only route to providers that honour the JSON schema.
            "provider": {"require_parameters": True},
        }

    def evaluate(self, content: str) -> BuddhiDetermination:
        """Evaluate content and determine importance, scope, categories, and whether to store.

        A model failure never raises: it returns a refusal (`store` false) with
        the error in `error` and in the trace.
        """
        started = time.monotonic()
        jev_future = self._start_jev(content)
        answer = {"provider": "openrouter", "model": self.model}
        try:
            data, meta = self._ask(content)
        except BuddhiError as err:
            logger.warning("Buddhi determination failed: %s", err)
            return BuddhiDetermination(
                importance=0.0,
                scope="/",
                categories=[],
                store=False,
                error=str(err),
                trace={
                    "decided_by": "buddhi",
                    "buddhi": {**answer, "status": "error", "error": str(err)},
                    "jev": self._finish_jev(jev_future, started),
                },
            )

        return BuddhiDetermination(
            importance=data["importance"],
            scope=data["scope"],
            categories=data["categories"],
            store=data["store"],
            trace={
                "decided_by": "buddhi",
                "buddhi": {**answer, "status": "ok", **meta, "response": data},
                "jev": self._finish_jev(jev_future, started),
            },
        )

    def _ask(self, content: str) -> tuple[dict, dict]:
        """One chat completion call. Returns the parsed answer and response metadata."""
        body = json.dumps(self.request_body(content)).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        started = time.monotonic()
        try:
            status, raw = self._transport(OPENROUTER_ENDPOINT, body, headers, BUDDHI_TIMEOUT_S)
        except Exception as err:
            raise BuddhiError(f"request failed: {type(err).__name__}: {err}") from err
        latency_ms = int((time.monotonic() - started) * 1000)

        if status != 200:
            snippet = raw[:200].decode(errors="replace").replace("\n", " ")
            raise BuddhiError(f"http {status}: {snippet}")
        try:
            response = json.loads(raw)
        except ValueError as err:
            raise BuddhiError("response is not JSON") from err
        if not isinstance(response, dict):
            raise BuddhiError("response is not a JSON object")
        if "error" in response:
            raise BuddhiError(f"provider error: {str(response['error'])[:200]}")
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise BuddhiError("response has no choices")
        choice = choices[0]
        if choice.get("finish_reason") not in (None, "stop"):
            raise BuddhiError(f"answer did not finish: {choice.get('finish_reason')}")
        message = choice.get("message")
        data = parse_determination(message.get("content") if isinstance(message, dict) else None)
        meta = {
            "model_version": response.get("model"),
            "served_by": response.get("provider"),
            "latency_ms": latency_ms,
        }
        return data, meta

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

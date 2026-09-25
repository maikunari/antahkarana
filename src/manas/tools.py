"""Manas — the I/O interface. MCP tool definitions for the Antaḥkaraṇa memory system."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from src.buddhi.jev import SECRET_THRESHOLD
from src.chitta.models import MemoryRecord
from src.dvarapala.keeper import Keeper, Scrubbed, default_keeper

if TYPE_CHECKING:
    from src.buddhi.embeddings import EmbeddingEngine
    from src.buddhi.engine import BuddhiEngine
    from src.chitta.models import BuddhiDetermination
    from src.chitta.store import ChittaStore

logger = logging.getLogger(__name__)

REDACTED_SECRET = "[redacted: likely secret]"

REDACTED_NOTE = (
    "{n} secret(s) removed before storage and before any model call; the value was not "
    "stored. Store a pointer instead (e.g. the 1Password item name)."
)
SECRET_ONLY_NOTE = (
    "Nothing but a secret was left to remember. Nothing was stored or sent to any model."
)
KEEPER_ERROR_NOTE = "The secrets keeper failed, so nothing was stored or sent to any model."
BUDDHI_ERROR_NOTE = (
    "Buddhi could not judge this content ({error}), so nothing was stored. Try again later."
)


def remember(
    content: str,
    *,
    chitta: ChittaStore,
    buddhi: BuddhiEngine,
    embeddings: EmbeddingEngine,
    scope: str | None = None,
    importance: float | None = None,
    source_agent: str | None = None,
    keeper: Keeper | None = None,
) -> dict:
    """Store a memory through the Antaḥkaraṇa pipeline.

    Dvārapāla scrubs every secret out of the caller's text first, so Buddhi,
    Jev, the embedder and Chitta only ever see the scrubbed text. Buddhi then
    evaluates it for importance, scope, and categories. If Buddhi determines
    the content should be stored, it is embedded and written to Chitta
    (Zvec + SQLite). Every determination and its outcome is logged to the
    determinations table.
    """
    try:
        keeper = keeper or default_keeper()
        scrubbed = keeper.scrub(content)
        scope_scrub = keeper.scrub(scope) if scope is not None else None
        agent_scrub = keeper.scrub(source_agent) if source_agent is not None else None
    except Exception:
        # Fail closed: no model call and no write without a working keeper.
        logger.error("Secrets keeper failed; refusing remember")
        return {"stored": False, "reason": "keeper_error", "note": KEEPER_ERROR_NOTE}

    # A caller scope or agent name holding a secret is dropped, not stored.
    if scope_scrub is not None and scope_scrub.redacted:
        scope = None
    if agent_scrub is not None and agent_scrub.redacted:
        source_agent = None
    redactions = _redactions(content=scrubbed, scope=scope_scrub, source_agent=agent_scrub)
    content = scrubbed.text

    if scrubbed.secret_only():
        trace = {"decided_by": "dvarapala", "redactions": redactions}
        final = {"store": False, "reason": "secret_only"}
        _log_trace(chitta, keeper, content, trace, source_agent, final)
        return {
            "stored": False,
            "reason": "secret_only",
            "redactions": redactions,
            "note": SECRET_ONLY_NOTE,
        }

    # Buddhi determination, on scrubbed text only
    determination = buddhi.evaluate(content)
    determination.trace["redactions"] = redactions

    if not determination.store:
        logged_input = REDACTED_SECRET if _likely_secret(determination) else content
        if determination.error is not None:
            final = {"store": False, "reason": "buddhi_error"}
            _log_determination(chitta, keeper, logged_input, determination, source_agent, final)
            note = keeper.scrub(BUDDHI_ERROR_NOTE.format(error=determination.error)).text
            result = _with_redactions({"stored": False, "reason": "buddhi_error"}, redactions)
            result["note"] = " ".join(n for n in (note, result.get("note")) if n)
            return result
        final = {"store": False}
        _log_determination(chitta, keeper, logged_input, determination, source_agent, final)
        return _with_redactions(
            {
                "stored": False,
                "reason": "Buddhi determined this content is too trivial to store.",
            },
            redactions,
        )

    # Build the memory record, allowing user overrides. Buddhi's scope and
    # categories are scrubbed too, in case the model echoed a secret.
    record = MemoryRecord(
        content=content,
        scope=scope if scope is not None else _clean_scope(keeper, determination.scope),
        importance=importance if importance is not None else determination.importance,
        categories=[c for c in determination.categories if not keeper.find(c)],
        source_agent=source_agent,
    )

    # Embed and store
    try:
        embedding = embeddings.embed(content)
        chitta.store(record, embedding)
    except Exception as err:
        final = {"store": False, "error": f"{type(err).__name__}: {err}"}
        _log_determination(chitta, keeper, content, determination, source_agent, final)
        raise

    final = {
        "store": True,
        "memory_id": record.id,
        "scope": record.scope,
        "importance": record.importance,
        "categories": record.categories,
    }
    _log_determination(chitta, keeper, content, determination, source_agent, final)

    return _with_redactions(
        {
            "stored": True,
            "memory_id": record.id,
            "scope": record.scope,
            "importance": record.importance,
            "categories": record.categories,
        },
        redactions,
    )


def _redactions(**fields: Scrubbed | None) -> list[dict]:
    """What was removed, by field and kind. Never the value or where it was."""
    return [
        {"field": name, "kind": kind, "count": count}
        for name, scrubbed in fields.items()
        if scrubbed is not None
        for kind, count in sorted(scrubbed.kinds().items())
    ]


def _with_redactions(result: dict, redactions: list[dict]) -> dict:
    if redactions:
        result["redactions"] = redactions
        result["note"] = REDACTED_NOTE.format(n=sum(r["count"] for r in redactions))
    return result


def _clean_scope(keeper: Keeper, scope: str) -> str:
    return "/" if keeper.find(scope) else scope


def _likely_secret(determination: BuddhiDetermination) -> bool:
    jev = determination.trace.get("jev", {})
    return jev.get("status") != "ok" or jev["secret_probability"] >= SECRET_THRESHOLD


def _log_determination(
    chitta: ChittaStore,
    keeper: Keeper,
    content: str,
    determination: BuddhiDetermination,
    source_agent: str | None,
    final: dict,
) -> None:
    _log_trace(chitta, keeper, content, determination.trace, source_agent, final)


def _log_trace(
    chitta: ChittaStore,
    keeper: Keeper,
    content: str,
    trace: dict,
    source_agent: str | None,
    final: dict,
) -> None:
    """Write the determination and its outcome to Chitta. A logging failure never fails remember.

    The whole row is scrubbed first: a model answer or an error string can
    echo text that the input scrub already removed from `content`.
    """
    try:
        row, _ = keeper.scrub_value({**trace, "source_agent": source_agent, "final": final})
        chitta.log_determination(content, row)
    except Exception:
        logger.warning("Could not log Buddhi determination", exc_info=True)


def recall(
    query: str,
    *,
    chitta: ChittaStore,
    embeddings: EmbeddingEngine,
    limit: int = 5,
    scope: str | None = None,
    include_latent: bool = False,
    keeper: Keeper | None = None,
) -> dict:
    """Retrieve relevant memories for a given context.

    Scrubs secrets out of the query, embeds it, performs semantic search in
    Zvec, joins with SQLite metadata, and returns composite-scored results.
    """
    try:
        scrubbed = (keeper or default_keeper()).scrub(query)
    except Exception:
        logger.error("Secrets keeper failed; refusing recall")
        return {"count": 0, "memories": [], "error": "keeper_error", "note": KEEPER_ERROR_NOTE}
    query = scrubbed.text
    query_embedding = embeddings.embed_query(query)

    results = chitta.search(
        query_embedding=query_embedding,
        limit=limit,
        scope=scope,
        include_latent=include_latent,
    )

    # Update recall stats for returned memories
    for result in results:
        chitta.update_recall_stats(result.memory_id)

    result = {
        "query": query,
        "count": len(results),
        "memories": [r.to_dict() for r in results],
    }
    if scrubbed.redacted:
        result["redactions"] = _redactions(query=scrubbed)
    return result


def forget(
    *,
    chitta: ChittaStore,
    memory_id: str | None = None,
    scope: str | None = None,
    force_dissolve: bool = False,
) -> dict:
    """Transition memories to latent or dissolved state.

    Targets a specific memory by ID, or all memories in a scope subtree.
    Latent keeps the content (it is reversible). Dissolved purges it: the
    memory's text, its vector, its determinations' input text and its
    feedback text are removed, leaving a trace record.
    """
    if not memory_id and not scope:
        return {
            "affected": 0,
            "error": "Must specify either memory_id or scope.",
        }

    new_state = "dissolved" if force_dissolve else "latent"
    reason = "User-requested forget" if force_dissolve else None

    affected = chitta.transition_state(
        memory_id=memory_id,
        scope=scope,
        new_state=new_state,
        reason=reason,
    )

    return {
        "affected": affected,
        "transitioned_to": new_state,
        "content_purged": force_dissolve and affected > 0,
    }

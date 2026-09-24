"""Manas — the I/O interface. MCP tool definitions for the Antaḥkaraṇa memory system."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from src.chitta.models import MemoryRecord

if TYPE_CHECKING:
    from src.buddhi.embeddings import EmbeddingEngine
    from src.buddhi.engine import BuddhiEngine
    from src.chitta.models import BuddhiDetermination
    from src.chitta.store import ChittaStore

logger = logging.getLogger(__name__)


def remember(
    content: str,
    *,
    chitta: ChittaStore,
    buddhi: BuddhiEngine,
    embeddings: EmbeddingEngine,
    scope: str | None = None,
    importance: float | None = None,
    source_agent: str | None = None,
) -> dict:
    """Store a memory through the Antaḥkaraṇa pipeline.

    Buddhi evaluates the content for importance, scope, and categories.
    If Buddhi determines the content should be stored, it is embedded
    and written to Chitta (Zvec + SQLite). Every determination and its
    outcome is logged to the determinations table.
    """
    # Buddhi determination
    determination = buddhi.evaluate(content)

    if not determination.store:
        _log_determination(chitta, content, determination, source_agent, {"store": False})
        return {
            "stored": False,
            "reason": "Buddhi determined this content is too trivial to store.",
        }

    # Build the memory record, allowing user overrides
    record = MemoryRecord(
        content=content,
        scope=scope if scope is not None else determination.scope,
        importance=importance if importance is not None else determination.importance,
        categories=determination.categories,
        source_agent=source_agent,
    )

    # Embed and store
    try:
        embedding = embeddings.embed(content)
        chitta.store(record, embedding)
    except Exception as err:
        final = {"store": False, "error": f"{type(err).__name__}: {err}"}
        _log_determination(chitta, content, determination, source_agent, final)
        raise

    final = {
        "store": True,
        "memory_id": record.id,
        "scope": record.scope,
        "importance": record.importance,
        "categories": record.categories,
    }
    _log_determination(chitta, content, determination, source_agent, final)

    return {
        "stored": True,
        "memory_id": record.id,
        "scope": record.scope,
        "importance": record.importance,
        "categories": record.categories,
    }


def _log_determination(
    chitta: ChittaStore,
    content: str,
    determination: BuddhiDetermination,
    source_agent: str | None,
    final: dict,
) -> None:
    """Write the determination and its outcome to Chitta. A logging failure never fails remember."""
    try:
        chitta.log_determination(
            content,
            {**determination.trace, "source_agent": source_agent, "final": final},
        )
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
) -> dict:
    """Retrieve relevant memories for a given context.

    Embeds the query, performs semantic search in Zvec, joins with SQLite
    metadata, and returns composite-scored results.
    """
    query_embedding = embeddings.embed(query)

    results = chitta.search(
        query_embedding=query_embedding,
        limit=limit,
        scope=scope,
        include_latent=include_latent,
    )

    # Update recall stats for returned memories
    for result in results:
        chitta.update_recall_stats(result.memory_id)

    return {
        "query": query,
        "count": len(results),
        "memories": [r.to_dict() for r in results],
    }


def forget(
    *,
    chitta: ChittaStore,
    memory_id: str | None = None,
    scope: str | None = None,
    force_dissolve: bool = False,
) -> dict:
    """Transition memories to latent or dissolved state.

    Targets a specific memory by ID, or all memories in a scope subtree.
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
    }

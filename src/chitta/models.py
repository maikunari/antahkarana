"""Data models for the Chitta memory store."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class MemoryRecord:
    """A single memory stored in Chitta."""

    content: str
    id: str = field(default_factory=_new_id)
    scope: str = "/"
    importance: float = 0.5
    categories: list[str] = field(default_factory=list)
    source_agent: str | None = None

    # Triguṇa scores (defaults for Phase 1, active in Phase 3)
    sattva: float = 0.33
    rajas: float = 0.34
    tamas: float = 0.33
    state: str = "active"  # active, in_flux, latent, dissolved

    # Zvec reference
    embedding_id: str | None = None

    # Timestamps
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    last_recalled_at: str | None = None
    recall_count: int = 0

    # Dissolution trace (Phase 3)
    dissolved_at: str | None = None
    dissolved_reason: str | None = None
    superseded_by: str | None = None

    @property
    def categories_json(self) -> str:
        return json.dumps(self.categories)

    @classmethod
    def from_row(cls, row: dict) -> MemoryRecord:
        """Create a MemoryRecord from a SQLite row dict."""
        categories = json.loads(row.get("categories", "[]"))
        return cls(
            id=row["id"],
            content=row["content"],
            scope=row.get("scope", "/"),
            importance=row.get("importance", 0.5),
            categories=categories,
            source_agent=row.get("source_agent"),
            sattva=row.get("sattva", 0.33),
            rajas=row.get("rajas", 0.34),
            tamas=row.get("tamas", 0.33),
            state=row.get("state", "active"),
            embedding_id=row.get("embedding_id"),
            created_at=row.get("created_at", _utc_now()),
            updated_at=row.get("updated_at", _utc_now()),
            last_recalled_at=row.get("last_recalled_at"),
            recall_count=row.get("recall_count", 0),
            dissolved_at=row.get("dissolved_at"),
            dissolved_reason=row.get("dissolved_reason"),
            superseded_by=row.get("superseded_by"),
        )


@dataclass
class BuddhiDetermination:
    """Result of Buddhi evaluating incoming content."""

    importance: float
    scope: str
    categories: list[str]
    store: bool
    # What each model answered, for the determinations log
    trace: dict = field(default_factory=dict)
    # Set when Buddhi's model failed and this determination is a refusal
    error: str | None = None


@dataclass
class RecallResult:
    """A single result from a recall query."""

    memory_id: str
    content: str
    scope: str
    importance: float
    score: float  # composite score
    state: str
    created_at: str
    last_recalled_at: str | None

    def to_dict(self) -> dict:
        return {
            "memory_id": self.memory_id,
            "content": self.content,
            "scope": self.scope,
            "importance": self.importance,
            "score": round(self.score, 4),
            "state": self.state,
            "created_at": self.created_at,
            "last_recalled_at": self.last_recalled_at,
        }

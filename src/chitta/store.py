"""Chitta — the unified Zvec + SQLite memory store.

Dual-write safety: SQLite first (transactional), then Zvec.
If Zvec write fails, SQLite transaction is rolled back.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import zvec

from src.chitta.models import MemoryRecord, RecallResult
from src.chitta.schema import init_db

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 768
RECENCY_HALF_LIFE_DAYS = 30.0


class ChittaStore:
    """Unified vector + structured memory store."""

    def __init__(self, data_dir: str | Path) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._db: sqlite3.Connection | None = None
        self._vec: zvec.Collection | None = None

    def init(self) -> None:
        """Initialize both SQLite and Zvec stores."""
        db_path = self._data_dir / "chitta.db"
        self._db = init_db(db_path)

        vec_path = str(self._data_dir / "chitta_vectors")
        schema = zvec.CollectionSchema(
            name="chitta",
            vectors=[
                zvec.VectorSchema(
                    name="embedding",
                    data_type=zvec.DataType.VECTOR_FP32,
                    dimension=EMBEDDING_DIM,
                ),
            ],
        )

        if Path(vec_path).exists():
            self._vec = zvec.open(vec_path)
        else:
            self._vec = zvec.create_and_open(vec_path, schema)

    def store(self, record: MemoryRecord, embedding: list[float]) -> None:
        """Store a memory record with dual-write safety.

        SQLite first (transactional), then Zvec. Rolls back SQLite if Zvec fails.
        """
        assert self._db is not None and self._vec is not None

        # Use the record ID as the Zvec document ID
        record.embedding_id = record.id

        cursor = self._db.cursor()
        try:
            cursor.execute(
                """INSERT INTO memories
                (id, content, scope, importance, categories, source_agent,
                 sattva, rajas, tamas, state, embedding_id,
                 created_at, updated_at, last_recalled_at, recall_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.id,
                    record.content,
                    record.scope,
                    record.importance,
                    record.categories_json,
                    record.source_agent,
                    record.sattva,
                    record.rajas,
                    record.tamas,
                    record.state,
                    record.embedding_id,
                    record.created_at,
                    record.updated_at,
                    record.last_recalled_at,
                    record.recall_count,
                ),
            )

            # Zvec write — if this fails, the SQLite transaction rolls back
            self._vec.insert(
                zvec.Doc(
                    id=record.id,
                    vectors={"embedding": embedding},
                )
            )

            self._db.commit()
        except Exception:
            self._db.rollback()
            # Attempt to clean up the Zvec doc if it was written
            try:
                self._vec.delete(record.id)
            except Exception:
                pass
            raise

    def search(
        self,
        query_embedding: list[float],
        limit: int = 5,
        scope: str | None = None,
        include_latent: bool = False,
    ) -> list[RecallResult]:
        """Semantic search with composite scoring.

        Score = 0.6 * similarity + 0.2 * importance + 0.2 * recency
        Recency uses exponential decay: 0.5 ** (days / 30)
        """
        assert self._db is not None and self._vec is not None

        # Search Zvec for top candidates (fetch more than limit for filtering)
        fetch_count = min(limit * 3, 50)
        results = self._vec.query(
            vectors=zvec.VectorQuery(
                field_name="embedding",
                vector=query_embedding,
            ),
            topk=fetch_count,
        )

        if not results:
            return []

        # Normalize similarity scores to 0-1 range (Zvec returns raw inner-product)
        doc_ids = [doc.id for doc in results]
        raw_scores = {doc.id: doc.score for doc in results}
        max_score = max(raw_scores.values()) if raw_scores else 1.0
        if max_score <= 0:
            max_score = 1.0
        similarity_scores = {
            doc_id: raw / max_score for doc_id, raw in raw_scores.items()
        }

        # Fetch metadata from SQLite
        placeholders = ",".join("?" * len(doc_ids))
        state_filter = "('active', 'in_flux')"
        if include_latent:
            state_filter = "('active', 'in_flux', 'latent')"

        scope_clause = ""
        params: list = list(doc_ids)
        if scope:
            scope_clause = "AND (scope = ? OR scope LIKE ?)"
            params.extend([scope, f"{scope}/%"])

        cursor = self._db.execute(
            f"""SELECT * FROM memories
            WHERE id IN ({placeholders})
            AND state IN {state_filter}
            {scope_clause}""",
            params,
        )
        rows = cursor.fetchall()

        # Compute composite scores
        now = datetime.now(timezone.utc)
        scored: list[RecallResult] = []
        for row in rows:
            row_dict = dict(row)
            memory_id = row_dict["id"]

            similarity = similarity_scores.get(memory_id, 0.0)
            importance = row_dict.get("importance", 0.5)

            created = datetime.fromisoformat(row_dict["created_at"])
            days_old = max(0.0, (now - created).total_seconds() / 86400)
            recency = 0.5 ** (days_old / RECENCY_HALF_LIFE_DAYS)

            composite = (0.6 * similarity) + (0.2 * importance) + (0.2 * recency)

            scored.append(
                RecallResult(
                    memory_id=memory_id,
                    content=row_dict["content"],
                    scope=row_dict.get("scope", "/"),
                    importance=importance,
                    score=composite,
                    state=row_dict.get("state", "active"),
                    created_at=row_dict["created_at"],
                    last_recalled_at=row_dict.get("last_recalled_at"),
                )
            )

        # Sort by composite score descending, return top `limit`
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:limit]

    def get(self, memory_id: str) -> MemoryRecord | None:
        """Fetch a single memory by ID."""
        assert self._db is not None
        cursor = self._db.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return MemoryRecord.from_row(dict(row))

    def update_recall_stats(self, memory_id: str) -> None:
        """Bump recall_count and last_recalled_at for a memory."""
        assert self._db is not None
        now = datetime.now(timezone.utc).isoformat()
        self._db.execute(
            """UPDATE memories
            SET recall_count = recall_count + 1,
                last_recalled_at = ?,
                updated_at = ?
            WHERE id = ?""",
            (now, now, memory_id),
        )
        self._db.commit()

    def transition_state(
        self,
        memory_id: str | None = None,
        scope: str | None = None,
        new_state: str = "latent",
        reason: str | None = None,
    ) -> int:
        """Transition memory/memories to a new state (for forget tool).

        Returns the number of affected rows.
        """
        assert self._db is not None
        now = datetime.now(timezone.utc).isoformat()

        if memory_id:
            dissolved_at = now if new_state == "dissolved" else None
            self._db.execute(
                """UPDATE memories
                SET state = ?, updated_at = ?, dissolved_at = ?, dissolved_reason = ?
                WHERE id = ? AND state != 'dissolved'""",
                (new_state, now, dissolved_at, reason, memory_id),
            )
            affected = self._db.execute("SELECT changes()").fetchone()[0]
        elif scope:
            dissolved_at = now if new_state == "dissolved" else None
            self._db.execute(
                """UPDATE memories
                SET state = ?, updated_at = ?, dissolved_at = ?, dissolved_reason = ?
                WHERE (scope = ? OR scope LIKE ?) AND state != 'dissolved'""",
                (new_state, now, dissolved_at, reason, scope, f"{scope}/%"),
            )
            affected = self._db.execute("SELECT changes()").fetchone()[0]
        else:
            affected = 0

        self._db.commit()
        return affected

    def close(self) -> None:
        """Close database connections."""
        if self._db:
            self._db.close()
            self._db = None
        self._vec = None

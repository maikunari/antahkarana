"""Chitta — the unified Zvec + SQLite memory store.

Dual-write safety: SQLite first (transactional), then Zvec.
If Zvec write fails, SQLite transaction is rolled back.

Every write that carries text passes the secrets keeper's check first, so a
code path that forgot to scrub fails loudly instead of storing a secret.
"""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import zvec

from src.chitta.models import MemoryRecord, RecallResult
from src.chitta.schema import init_db
from src.dvarapala.keeper import Keeper, default_keeper

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 768
RECENCY_HALF_LIFE_DAYS = 30.0
VECTOR_DIR = "chitta_vectors"
# What a dissolved memory's content, and its determinations' input, become.
DISSOLVED_CONTENT = "[dissolved]"


def _vector_schema() -> zvec.CollectionSchema:
    return zvec.CollectionSchema(
        name="chitta",
        vectors=[
            zvec.VectorSchema(
                name="embedding",
                data_type=zvec.DataType.VECTOR_FP32,
                dimension=EMBEDDING_DIM,
            ),
        ],
    )


class ChittaStore:
    """Unified vector + structured memory store."""

    def __init__(self, data_dir: str | Path, keeper: Keeper | None = None) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._db: sqlite3.Connection | None = None
        self._vec: zvec.Collection | None = None
        self._keeper = keeper or default_keeper()

    def init(self) -> None:
        """Initialize both SQLite and Zvec stores."""
        db_path = self._data_dir / "chitta.db"
        self._db = init_db(db_path)

        vec_path = self._data_dir / VECTOR_DIR
        rebuilt = self._data_dir / f"{VECTOR_DIR}.rebuild"
        if not vec_path.exists() and rebuilt.exists():
            rebuilt.rename(vec_path)  # a compaction stopped between destroy and rename

        if vec_path.exists():
            self._vec = zvec.open(str(vec_path))
        else:
            self._vec = zvec.create_and_open(str(vec_path), _vector_schema())

    def store(self, record: MemoryRecord, embedding: list[float]) -> None:
        """Store a memory record with dual-write safety.

        SQLite first (transactional), then Zvec. Rolls back SQLite if Zvec fails.
        Raises SecretInWrite, before writing anything, if the record holds a secret.
        """
        self._keeper.check(
            "memories", record.content, record.scope, record.source_agent, record.categories
        )
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

        Dissolving also purges the memory everywhere (see `dissolve`). Any
        other state keeps the content, since it is reversible.

        Returns the number of affected rows.
        """
        assert self._db is not None
        if memory_id:
            where, params = "id = ?", [memory_id]
        elif scope:
            where, params = "(scope = ? OR scope LIKE ?)", [scope, f"{scope}/%"]
        else:
            return 0
        ids = [
            row[0]
            for row in self._db.execute(
                f"SELECT id FROM memories WHERE {where} AND state != 'dissolved'", params
            )
        ]
        if new_state == "dissolved":
            return self.dissolve(ids, reason)

        self._keeper.check("memories.dissolved_reason", reason)
        now = datetime.now(timezone.utc).isoformat()
        self._db.executemany(
            """UPDATE memories
            SET state = ?, updated_at = ?, dissolved_at = NULL, dissolved_reason = ?
            WHERE id = ?""",
            [(new_state, now, reason, i) for i in ids],
        )
        self._db.commit()
        return len(ids)

    def dissolve(self, ids: list[str], reason: str | None) -> int:
        """Dissolve memories, leaving only a trace record, and purge their content."""
        assert self._db is not None
        self._keeper.check("memories.dissolved_reason", reason)
        now = datetime.now(timezone.utc).isoformat()
        self._db.executemany(
            """UPDATE memories
            SET state = 'dissolved', updated_at = ?, dissolved_at = ?, dissolved_reason = ?
            WHERE id = ?""",
            [(now, now, reason, i) for i in ids],
        )
        return self.purge_content(ids)

    def purge_content(self, ids: list[str]) -> int:
        """Remove memories' text from every table and their vectors from the index.

        The row keeps its id, scope, categories, scores and dates as the trace.
        Linked determinations lose their input text and linked feedback its
        free text. SQLite overwrites the old pages (secure_delete) and the WAL
        is truncated; the vector bytes stay in Zvec's files until `compact`.
        """
        assert self._db is not None
        if not ids:
            self._db.commit()
            return 0
        self._db.executemany(
            "UPDATE memories SET content = ? WHERE id = ?",
            [(DISSOLVED_CONTENT, i) for i in ids],
        )
        self._db.executemany(
            "UPDATE determinations SET input_text = ? WHERE memory_id = ?",
            [(DISSOLVED_CONTENT, i) for i in ids],
        )
        self._db.executemany(
            "UPDATE feedback SET context = NULL, details = NULL WHERE memory_id = ?",
            [(i,) for i in ids],
        )
        self._db.commit()
        self._delete_vectors(ids)
        self.checkpoint()
        return len(ids)

    def rewrite_memory(
        self,
        memory_id: str,
        *,
        content: str,
        scope: str,
        categories: list[str],
        source_agent: str | None,
        embedding: list[float] | None = None,
    ) -> None:
        """Replace a memory's text in place, and its vector when `embedding` is given."""
        assert self._db is not None
        self._keeper.check("memories", content, scope, source_agent, categories)
        self._db.execute(
            """UPDATE memories
            SET content = ?, scope = ?, categories = ?, source_agent = ?, updated_at = ?
            WHERE id = ?""",
            (
                content,
                scope,
                json.dumps(categories),
                source_agent,
                datetime.now(timezone.utc).isoformat(),
                memory_id,
            ),
        )
        self._db.commit()
        if embedding is not None:
            assert self._vec is not None
            self._delete_vectors([memory_id])
            self._vec.insert(zvec.Doc(id=memory_id, vectors={"embedding": embedding}))

    def rewrite_determination(
        self, determination_id: str, input_text: str, determination: str
    ) -> None:
        assert self._db is not None
        self._keeper.check("determinations", input_text, determination)
        self._db.execute(
            "UPDATE determinations SET input_text = ?, determination = ? WHERE id = ?",
            (input_text, determination, determination_id),
        )
        self._db.commit()

    def rewrite_feedback(self, feedback_id: str, context: str | None, details: str | None) -> None:
        assert self._db is not None
        self._keeper.check("feedback", context, details)
        self._db.execute(
            "UPDATE feedback SET context = ?, details = ? WHERE id = ?",
            (context, details, feedback_id),
        )
        self._db.commit()

    def checkpoint(self) -> None:
        """Copy the WAL into the database and truncate it, so old page images are gone."""
        assert self._db is not None
        self._db.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def compact(self) -> int:
        """Physically remove purged data. Returns the number of vectors kept.

        VACUUM rewrites the SQLite file. Zvec's delete only hides a vector (its
        bytes stay in the index files, even after optimize), so the collection
        is rebuilt from the vectors of memories that are not dissolved.
        """
        assert self._db is not None and self._vec is not None
        self.checkpoint()
        self._db.execute("VACUUM")
        self.checkpoint()

        live = {
            row[0]
            for row in self._db.execute("SELECT id FROM memories WHERE state != 'dissolved'")
        }
        vec_path = self._data_dir / VECTOR_DIR
        rebuilt = self._data_dir / f"{VECTOR_DIR}.rebuild"
        if rebuilt.exists():
            shutil.rmtree(rebuilt)
        fresh = zvec.create_and_open(str(rebuilt), _vector_schema())
        kept = 0
        for doc in self._vec.iter_docs():
            if doc.id in live:
                fresh.insert(
                    zvec.Doc(id=doc.id, vectors={"embedding": list(doc.vectors["embedding"])})
                )
                kept += 1
        fresh.flush()
        fresh.close()
        self._vec.destroy()
        self._vec = None
        rebuilt.rename(vec_path)
        self._vec = zvec.open(str(vec_path))
        return kept

    def _delete_vectors(self, ids: list[str]) -> None:
        if self._vec is None or not ids:
            return
        try:
            self._vec.delete(list(ids))
            self._vec.flush()
        except Exception:
            logger.warning(
                "Could not delete %d vector(s); `python -m src.dvarapala purge` removes them",
                len(ids),
                exc_info=True,
            )

    def log_determination(self, input_text: str, determination: dict) -> str:
        """Record one Buddhi determination in the determinations table. Returns its ID.

        The row is linked to the memory it stored (`final.memory_id`), so
        dissolving that memory also purges this row's input text.
        """
        assert self._db is not None
        self._keeper.check("determinations", input_text, determination)
        determination_id = str(uuid.uuid4())
        final = determination.get("final")
        memory_id = final.get("memory_id") if isinstance(final, dict) else None
        self._db.execute(
            """INSERT INTO determinations (id, input_text, determination, created_at, memory_id)
            VALUES (?, ?, ?, ?, ?)""",
            (
                determination_id,
                input_text,
                json.dumps(determination),
                datetime.now(timezone.utc).isoformat(),
                memory_id,
            ),
        )
        self._db.commit()
        return determination_id

    def close(self) -> None:
        """Close database connections."""
        if self._db:
            self._db.close()
            self._db = None
        self._vec = None

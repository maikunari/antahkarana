"""SQLite schema definitions and initialization for Chitta."""

import sqlite3
from pathlib import Path

SCHEMA_SQL = """
-- Core memory records
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    scope TEXT DEFAULT '/',
    importance REAL DEFAULT 0.5,
    categories TEXT DEFAULT '[]',
    source_agent TEXT,

    -- Triguṇa scores (Phase 3, defaults for now)
    sattva REAL DEFAULT 0.33,
    rajas REAL DEFAULT 0.34,
    tamas REAL DEFAULT 0.33,
    state TEXT DEFAULT 'active',

    -- Zvec reference
    embedding_id TEXT,

    -- Timestamps
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_recalled_at TEXT,
    recall_count INTEGER DEFAULT 0,

    -- Dissolution trace (Phase 3)
    dissolved_at TEXT,
    dissolved_reason TEXT,
    superseded_by TEXT
);

-- Feedback / meta-vāsanās (Phase 5)
CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY,
    memory_id TEXT,
    feedback_type TEXT NOT NULL,
    context TEXT,
    details TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (memory_id) REFERENCES memories(id)
);

-- Buddhi determination log (for Adhyavasāya learning)
CREATE TABLE IF NOT EXISTS determinations (
    id TEXT PRIMARY KEY,
    input_text TEXT NOT NULL,
    determination TEXT NOT NULL,
    feedback_id TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (feedback_id) REFERENCES feedback(id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_memories_scope ON memories(scope);
CREATE INDEX IF NOT EXISTS idx_memories_state ON memories(state);
CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance);
CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);
CREATE INDEX IF NOT EXISTS idx_memories_sattva ON memories(sattva);
"""


def init_db(db_path: str | Path) -> sqlite3.Connection:
    """Initialize the SQLite database, creating tables if needed.

    Returns an open connection with row_factory set to sqlite3.Row.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn

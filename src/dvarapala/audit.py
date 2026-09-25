"""Find and purge secrets already stored in Chitta.

`audit` is read-only: it scans every text column with the keeper and reports
counts by table, column and kind, plus the affected row ids. It never prints
a secret value or its position.

`purge` rewrites what the audit found: memories are scrubbed and re-embedded
from the scrubbed text (or dissolved when nothing but the secret is left),
determination and feedback text is scrubbed, dissolved memories that still
hold content are purged, and then SQLite is vacuumed and the vector index
rebuilt so the old bytes are gone. It finishes by re-auditing and
byte-searching every data file for the values it removed.

Neither can reach copies outside the data directory (backups, snapshots) or
text already sent to Gemini or Jev: rotate what the audit lists.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from src.chitta.store import DISSOLVED_CONTENT, ChittaStore
from src.dvarapala.keeper import Finding, Keeper, Scrubbed

PURGE_REASON = "Secret purged by the secrets keeper"
# Shorter values (a PIN, say) would match unrelated bytes in the byte search.
MIN_VERIFY_LENGTH = 8


class EmbedderRequired(Exception):
    """Purge would re-embed scrubbed memories but has no embedder. Raised before any write."""


@dataclass
class Hit:
    table: str
    column: str
    row_id: str
    kinds: list[str]
    created_at: str | None
    source_agent: str | None = None


@dataclass
class AuditReport:
    hits: list[Hit] = field(default_factory=list)
    # Dissolved before dissolving purged: the content is still in the row.
    unpurged_dissolved: list[str] = field(default_factory=list)
    # The secret values found, held in memory only, for the byte-search check.
    _values: set[str] = field(default_factory=set, repr=False)

    @property
    def clean(self) -> bool:
        return not self.hits and not self.unpurged_dissolved

    def counts(self) -> Counter:
        return Counter((h.table, h.column, k) for h in self.hits for k in h.kinds)

    def rotation(self) -> dict[str, tuple[str, str]]:
        """Each kind found, with the first and last time a row holding it was written."""
        spans: dict[str, tuple[str, str]] = {}
        for h in self.hits:
            when = h.created_at or "?"
            for kind in h.kinds:
                first, last = spans.get(kind, (when, when))
                spans[kind] = (min(first, when), max(last, when))
        return spans

    def lines(self) -> list[str]:
        if self.clean:
            return ["No secrets found, and every dissolved memory is purged."]
        out = []
        if self.hits:
            out.append(f"Secrets found: {sum(self.counts().values())} in {len(self.hits)} field(s)")
            for (table, column, kind), n in sorted(self.counts().items()):
                out.append(f"  {table}.{column}  {kind}  x{n}")
            out.append("Rows:")
            for h in self.hits:
                agent = f"  agent={h.source_agent}" if h.source_agent else ""
                out.append(f"  {h.table} {h.row_id}  {h.column}  {h.created_at}{agent}")
            out.append(
                "Rotate these credentials: text stored before the keeper existed was sent "
                "to Gemini (and to Jev when TYPESAFE_API_KEY was set). Purging does not "
                "un-send it."
            )
            for kind, (first, last) in sorted(self.rotation().items()):
                out.append(f"  {kind}  stored {first} .. {last}")
        if self.unpurged_dissolved:
            out.append(
                f"Dissolved memories still holding content: {len(self.unpurged_dissolved)}"
            )
        return out


def _open_readonly(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _values(text: str, findings: list[Finding]) -> set[str]:
    return {text[f.start:f.end] for f in findings}


def audit(db_path: Path, keeper: Keeper) -> AuditReport:
    """Scan every text column in `db_path` for secrets. Read-only."""
    report = AuditReport()

    def scan(table: str, column: str, row: sqlite3.Row, value: object, agent=None) -> None:
        if value is None:
            return
        findings: list[Finding] = []
        for text in _strings(value):
            found = keeper.find(text)
            findings += found
            report._values |= _values(text, found)
        if findings:
            kinds = sorted({f.rule_id for f in findings})
            report.hits.append(Hit(table, column, row["id"], kinds, row["created_at"], agent))

    conn = _open_readonly(db_path)
    try:
        for row in conn.execute("SELECT * FROM memories"):
            if row["state"] == "dissolved" and row["content"] != DISSOLVED_CONTENT:
                report.unpurged_dissolved.append(row["id"])
            agent = row["source_agent"]
            safe_agent = agent if agent and not keeper.find(agent) else None
            scan("memories", "content", row, row["content"], safe_agent)
            scan("memories", "scope", row, row["scope"], safe_agent)
            scan("memories", "categories", row, _json(row["categories"]), safe_agent)
            scan("memories", "source_agent", row, agent)
        for row in conn.execute("SELECT * FROM determinations"):
            payload = _json(row["determination"])
            agent = payload.get("source_agent") if isinstance(payload, dict) else None
            safe_agent = agent if isinstance(agent, str) and not keeper.find(agent) else None
            scan("determinations", "input_text", row, row["input_text"], safe_agent)
            scan("determinations", "determination", row, payload, safe_agent)
        for row in conn.execute("SELECT * FROM feedback"):
            scan("feedback", "context", row, row["context"])
            scan("feedback", "details", row, row["details"])
    finally:
        conn.close()
    return report


def purge(
    data_dir: Path,
    keeper: Keeper,
    embed: Callable[[str], list[float]] | None,
) -> tuple[AuditReport, AuditReport, int]:
    """Remove every secret found by `audit`, then compact and verify.

    `embed` re-embeds memories whose content was scrubbed; it only ever sees
    scrubbed text. Returns (before, after, files still holding a found value).
    """
    db_path = Path(data_dir) / "chitta.db"
    before = audit(db_path, keeper)
    memories = _hit_memories(db_path, keeper, before)
    to_embed = sum(1 for row, content in memories if _re_embeds(row, content))
    if to_embed and embed is None:
        raise EmbedderRequired(
            f"{to_embed} memories need re-embedding after scrubbing; set GEMINI_API_KEY"
        )

    chitta = ChittaStore(data_dir, keeper=keeper)
    chitta.init()
    try:
        _purge_memories(chitta, keeper, memories, embed)
        chitta.purge_content(before.unpurged_dissolved)
        _purge_logs(chitta, db_path, keeper, before)
        chitta.compact()
    finally:
        chitta.close()

    after = audit(db_path, keeper)
    return before, after, _files_holding(Path(data_dir), before._values)


def _hit_memories(db_path, keeper, report) -> list[tuple[sqlite3.Row, Scrubbed]]:
    """Each memory the audit hit, with its content scrubbed."""
    ids = sorted({h.row_id for h in report.hits if h.table == "memories"})
    if not ids:
        return []
    conn = _open_readonly(db_path)
    try:
        rows = {r["id"]: r for r in conn.execute(
            f"SELECT * FROM memories WHERE id IN ({','.join('?' * len(ids))})", ids
        )}
    finally:
        conn.close()
    return [(rows[i], keeper.scrub(rows[i]["content"])) for i in ids]


def _re_embeds(row: sqlite3.Row, content: Scrubbed) -> bool:
    """A memory that stays active with scrubbed content needs a new vector."""
    return row["state"] != "dissolved" and content.redacted and not content.secret_only()


def _purge_memories(chitta, keeper, memories, embed) -> None:
    for row, content in memories:
        memory_id = row["id"]
        dissolved = row["state"] == "dissolved"
        if not dissolved and content.secret_only():
            chitta.dissolve([memory_id], PURGE_REASON)
            continue
        categories = _json(row["categories"]) or []
        agent = row["source_agent"]
        new_content = DISSOLVED_CONTENT if dissolved else content.text
        chitta.rewrite_memory(
            memory_id,
            content=new_content,
            scope="/" if keeper.find(row["scope"] or "") else row["scope"],
            categories=[c for c in categories if not keeper.find(str(c))],
            source_agent=None if agent and keeper.find(agent) else agent,
            embedding=embed(new_content) if _re_embeds(row, content) else None,
        )


def _purge_logs(chitta, db_path, keeper, report) -> None:
    conn = _open_readonly(db_path)
    try:
        for table in ("determinations", "feedback"):
            ids = sorted({h.row_id for h in report.hits if h.table == table})
            for row_id in ids:
                row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
                if row is None:
                    continue
                if table == "determinations":
                    payload, _ = keeper.scrub_value(_json(row["determination"]))
                    chitta.rewrite_determination(
                        row_id, keeper.scrub(row["input_text"]).text, json.dumps(payload)
                    )
                else:
                    chitta.rewrite_feedback(
                        row_id,
                        keeper.scrub(row["context"]).text if row["context"] else row["context"],
                        keeper.scrub(row["details"]).text if row["details"] else row["details"],
                    )
    finally:
        conn.close()


def _files_holding(data_dir: Path, values: set[str]) -> int:
    needles = [v.encode() for v in values if len(v) >= MIN_VERIFY_LENGTH]
    if not needles:
        return 0
    count = 0
    for path in data_dir.rglob("*"):
        if path.is_file():
            data = path.read_bytes()
            if any(n in data for n in needles):
                count += 1
    return count


def _json(text: object) -> object:
    if not isinstance(text, str):
        return text
    try:
        return json.loads(text)
    except ValueError:
        return text


def _strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _strings(k)
            yield from _strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _strings(v)

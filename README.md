# Antaḥkaraṇa

A platform-agnostic persistent memory layer for AI agents, built as a standalone MCP server. Plug it into Claude Code, OpenClaw, Cowork, or any MCP-compatible client — your knowledge persists across every tool you use. The architecture is grounded in the Vedic Antaḥkaraṇa (inner instruments of mind) framework: Buddhi (Gemini Flash) evaluates every input before Chitta (Zvec + SQLite) stores it, so memory is discriminated, not just accumulated.

## Quick Start

```bash
cd antahkarana
python3.12 -m venv .venv
source .venv/bin/activate
pip install mcp zvec google-genai pyyaml python-dotenv
```

Create `.env`:

```
GEMINI_API_KEY=your_key_here
# Optional: Jev shadow judge (see "Determination log and Jev shadow mode")
TYPESAFE_API_KEY=
```

Run the server directly:

```bash
python -m src
```

Run the tests (no network or API keys needed):

```bash
pip install pytest
python -m pytest
```

## Connecting to Claude Code

Add to `~/.claude/claude_code_config.json`:

```json
{
  "mcpServers": {
    "antahkarana": {
      "command": "/path/to/antahkarana/.venv/bin/python",
      "args": ["-m", "src"],
      "cwd": "/path/to/antahkarana"
    }
  }
}
```

## Connecting to OpenClaw

Add as an MCP tool source. The server uses stdio transport — point your MCP client at the same command:

```
command: /path/to/antahkarana/.venv/bin/python
args: ["-m", "src"]
cwd: /path/to/antahkarana
```

Any MCP-compatible client can connect the same way.

## Tools

### `remember`

Store a memory through the Buddhi evaluation pipeline.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | yes | The text to remember |
| `scope` | string | no | Override Buddhi's scope inference (e.g. `/project/jozu/architecture`) |
| `importance` | float | no | Override Buddhi's importance assessment (0.0–1.0) |
| `source_agent` | string | no | Which agent is storing this (`claude-code`, `openclaw`, etc.) |

Returns: `memory_id`, `scope`, `importance`, `categories`, or `stored: false` if Buddhi determines the content is too trivial.

### `recall`

Retrieve relevant memories via semantic search with composite scoring.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | yes | What to search for |
| `limit` | int | no | Max results (default 5) |
| `scope` | string | no | Restrict to a scope subtree |
| `include_latent` | bool | no | Include dormant memories (default false) |

Returns: Ranked list of memories with `content`, `scope`, `importance`, `score`, `state`.

Scoring: `0.6 * semantic_similarity + 0.2 * importance + 0.2 * recency` (30-day half-life exponential decay).

### `forget`

Transition memories to latent (dormant) or dissolved (trace only) state.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `memory_id` | string | no* | Specific memory to forget |
| `scope` | string | no* | Target all memories in this scope subtree |
| `force_dissolve` | bool | no | Skip latent, go straight to dissolved (default false) |

\* At least one of `memory_id` or `scope` is required.

## Determination log and Jev shadow mode

Every `remember` call writes one row to the `determinations` table in `chitta.db`: the input text in `input_text` (a refused input Jev flags as a likely secret is logged as `[redacted: likely secret]` instead), and a JSON `determination` holding Gemini's model id and raw JSON answer, the Jev shadow answer, `decided_by`, the `source_agent`, and the `final` outcome (stored or not, with the memory ID, scope, importance and categories after caller overrides). A logging failure never fails `remember`.

With `TYPESAFE_API_KEY` set, Buddhi also asks TypeSafe's Jev (`src/buddhi/jev.py`, pinned to `jev-1.13.0`) the keep-or-discard question, in parallel with Gemini. Jev sees only the memory text. Its answer (kind, per-kind probabilities, keep probability, secret probability, would-store) is logged, and **Gemini's `store` still decides**. Any Jev error, or no answer within 3 s of the call starting, is logged as `error` or `timeout` and changes nothing. Without the key, Jev is off.

Inspect disagreements:

```bash
sqlite3 data/chitta.db "SELECT input_text, determination FROM determinations
  WHERE json_extract(determination, '$.jev.status') = 'ok'
    AND json_extract(determination, '$.jev.store') != json_extract(determination, '$.gemini.response.store')"
```

## Project Structure

```
antahkarana/
├── config/
│   ├── buddhi_prompt.yaml      # Buddhi determination prompt
│   └── ahamkara.yaml           # Identity config (Phase 4)
├── src/
│   ├── server.py               # MCP server entry point (Prāṇa)
│   ├── chitta/
│   │   ├── models.py           # MemoryRecord, RecallResult dataclasses
│   │   ├── schema.py           # SQLite DDL + init
│   │   └── store.py            # Zvec + SQLite unified store
│   ├── buddhi/
│   │   ├── engine.py           # Gemini Flash determination
│   │   ├── prompts.py          # Prompt loading from YAML
│   │   ├── jev.py              # Jev keep-or-discard judge (shadow mode)
│   │   └── embeddings.py       # Gemini embedding wrapper (768-dim)
│   ├── manas/
│   │   └── tools.py            # remember, recall, forget logic
│   ├── guna/
│   │   └── engine.py           # stub (Phase 3)
│   ├── ahamkara/
│   │   └── identity.py         # stub (Phase 4)
│   └── adhyavasaya/
│       └── feedback.py         # stub (Phase 5)
├── tests/                      # pytest; fixtures/buddhi_examples.yaml holds kept/refused examples
└── data/                       # Runtime data (gitignored)
    ├── chitta.db               # SQLite
    └── chitta_vectors/         # Zvec collection
```

## Phases

**Phase 1 — Core Loop (current)**
Remember + recall + forget. Buddhi evaluates importance/scope/categories via Gemini Flash. Chitta stores in Zvec (semantic vectors) + SQLite (metadata) with dual-write transactional safety.

**Phase 2 — Buddhi Intelligence**
Consolidation on save, atomic fact extraction, contradiction detection, smarter scope inference.

**Phase 3 — Triguṇa Engine**
Dynamic Sattva/Rajas/Tamas scoring. Memories drift toward clarity (active), activity (in flux), or dormancy (latent) based on lifecycle events. System health diagnostics.

**Phase 4 — Ahaṃkāra (Identity)**
Identity-aware memory. Buddhi incorporates persona, active projects, and preferences when making determinations.

**Phase 5 — Adhyavasāya (Learning)**
Feedback loop. User corrections stored as meta-vāsanās. Buddhi's determination criteria improve over time.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Reasoning (Buddhi) | Gemini 2.5 Flash |
| Keep-or-discard shadow judge | TypeSafe Jev (`jev-1.13.0`), optional |
| Embeddings | `gemini-embedding-001` @ 768 dims |
| Vector store (Chitta) | Zvec |
| Structured store | SQLite |
| MCP framework | `mcp` Python SDK (FastMCP) |
| Transport | stdio |

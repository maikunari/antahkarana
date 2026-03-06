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
```

Run the server directly:

```bash
python -m src
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
│   │   └── embeddings.py       # Gemini embedding wrapper (768-dim)
│   ├── manas/
│   │   └── tools.py            # remember, recall, forget logic
│   ├── guna/
│   │   └── engine.py           # stub (Phase 3)
│   ├── ahamkara/
│   │   └── identity.py         # stub (Phase 4)
│   └── adhyavasaya/
│       └── feedback.py         # stub (Phase 5)
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
| Embeddings | `gemini-embedding-001` @ 768 dims |
| Vector store (Chitta) | Zvec |
| Structured store | SQLite |
| MCP framework | `mcp` Python SDK (FastMCP) |
| Transport | stdio |

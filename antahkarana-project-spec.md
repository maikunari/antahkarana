# Antaḥkaraṇa — Project Specification

## Overview

Build a Python MCP server that provides a platform-agnostic persistent memory layer for AI agents. Any MCP-compatible client (Claude Code, OpenClaw, Cowork, Gemini workflows, etc.) connects to this server and gains access to intelligent, persistent memory.

The architecture is based on the Vedic Antaḥkaraṇa (inner instruments of mind) framework. Read the accompanying whitepaper (`antahkarana-whitepaper.docx`) for the full philosophical and architectural rationale.

---

## Tech Stack

| Component | Technology | Role |
|-----------|-----------|------|
| Runtime | Python 3.12+ | MCP server + all processing |
| MCP Framework | `mcp` Python SDK | Server, tool definitions, transport |
| Vector Store | Zvec (by Alibaba) | Semantic search in Chitta |
| Structured Store | SQLite (via `sqlite3`) | Metadata, guṇa scores, state, relationships |
| Reasoning (Buddhi) | Google Gemini 2.5 Flash API | Determination, classification, consolidation |
| Embeddings | Google Gemini Embedding API | Text → vector conversion (free tier) |
| Identity (Ahamkāra) | YAML config files | Persona, preferences, project contexts |
| Transport | stdio (primary), SSE (optional) | MCP client communication |

---

## Project Structure

```
antahkarana/
├── README.md
├── pyproject.toml
├── .env.example                  # GEMINI_API_KEY, etc.
├── config/
│   ├── ahamkara.yaml             # Identity/persona config
│   └── buddhi_prompt.yaml        # Buddhi determination prompts (evolves over time)
├── src/
│   ├── __init__.py
│   ├── server.py                 # MCP server entry point (Prāṇa)
│   ├── chitta/
│   │   ├── __init__.py
│   │   ├── store.py              # Zvec + SQLite unified interface
│   │   ├── schema.py             # SQLite schema definitions
│   │   └── models.py             # Memory record dataclasses
│   ├── buddhi/
│   │   ├── __init__.py
│   │   ├── engine.py             # Determination logic (encode, recall, consolidate)
│   │   ├── prompts.py            # Prompt templates for Gemini Flash
│   │   └── embeddings.py         # Gemini embedding wrapper
│   ├── ahamkara/
│   │   ├── __init__.py
│   │   └── identity.py           # Load and apply identity config
│   ├── manas/
│   │   ├── __init__.py
│   │   └── tools.py              # MCP tool definitions (the I/O interface)
│   ├── guna/
│   │   ├── __init__.py
│   │   └── engine.py             # Triguṇa scoring and state transitions
│   └── adhyavasaya/
│       ├── __init__.py
│       └── feedback.py           # RL feedback loop, meta-vāsanā storage
├── data/                         # Runtime data (gitignored)
│   ├── chitta.db                 # SQLite database
│   ├── chitta_vectors/           # Zvec collection directory
│   └── adhyavasaya/              # Feedback examples (JSON)
└── tests/
    ├── test_chitta.py
    ├── test_buddhi.py
    ├── test_guna.py
    └── test_integration.py
```

---

## Build Phases

### Phase 1: Core Loop (remember + recall)
Get the basic pipeline working end-to-end. This is the MVP.

**Deliverables:**
- MCP server starts and accepts connections via stdio
- `remember` tool: text in → Buddhi evaluates → Chitta stores (Zvec + SQLite)
- `recall` tool: query in → Zvec semantic search → composite scored results out
- SQLite schema with memory records (content, embedding_id, importance, scope, timestamps)
- Basic Buddhi prompt that evaluates importance (0-1) and suggests scope
- Gemini embedding integration for text → vector

**Skip for now:** Guṇa scores, Ahamkāra, consolidation, feedback loop.

### Phase 2: Buddhi Intelligence
Make the determination layer actually smart.

**Deliverables:**
- Consolidation on save: before storing, search Chitta for similar memories. If found, Buddhi determines: keep both, update existing, or replace.
- Atomic extraction: a `extract_and_remember` tool that takes raw text, breaks it into discrete facts via Buddhi, then stores each fact independently.
- Scope inference: Buddhi suggests hierarchical scope paths (e.g., `/project/jozu/architecture`) based on content analysis.
- Contradiction detection: Buddhi flags when new information contradicts existing memories.

### Phase 3: Triguṇa Engine
Add the dynamic scoring system.

**Deliverables:**
- Add `sattva`, `rajas`, `tamas` float columns to SQLite schema.
- Initial guṇa assignment by Buddhi at encoding time.
- Guṇa updates on lifecycle events:
  - Memory recalled → Sattva boost, Tamas reduction
  - Memory involved in consolidation → Rajas boost
  - Memory not recalled for N days → Tamas drift
  - User feedback received → Rajas boost
- Memory state derived from predominant guṇa: Active (Sattva), In Flux (Rajas), Latent (Tamas)
- Latent memories excluded from standard recall, included only on high-similarity direct match.
- Dissolution: Buddhi-confirmed pruning of fully Tāmasic + superseded memories, leaving trace records.
- `system_health` tool: returns guṇa distribution across all memories (healthy/stagnating/churning/overloaded diagnosis).

### Phase 4: Ahamkāra (Identity Layer)
Add identity-aware memory.

**Deliverables:**
- Load `ahamkara.yaml` at startup. Config includes: name, role, projects, preferences, boundaries.
- Buddhi incorporates Ahamkāra context when determining importance and scope ("is this relevant to my current projects?").
- Identity-scoped recall: memories tagged with Ahamkāra relevance are boosted in scoring.
- `update_identity` tool: modify Ahamkāra config at runtime.

### Phase 5: Adhyavasāya (Learning Loop)
Make the system improve over time.

**Deliverables:**
- `feedback` tool: user marks a recall result as "helpful" or "irrelevant", or tells the system "you should have remembered X".
- Feedback stored as labeled meta-vāsanās in `data/adhyavasaya/`.
- Periodic synthesis: every N feedback items, summarize patterns into updated Buddhi determination guidelines.
- Buddhi prompt dynamically augmented with learned guidelines from `buddhi_prompt.yaml`.
- Guṇa transition thresholds adjusted based on feedback patterns.

---

## SQLite Schema (Phase 1, extended in later phases)

```sql
-- Core memory records
CREATE TABLE memories (
    id TEXT PRIMARY KEY,                    -- UUID
    content TEXT NOT NULL,                  -- The actual memory text
    scope TEXT DEFAULT '/',                 -- Hierarchical scope path
    importance REAL DEFAULT 0.5,           -- 0.0 to 1.0
    categories TEXT DEFAULT '[]',           -- JSON array of category strings
    source_agent TEXT,                      -- Which agent stored this (claude-code, openclaw, etc.)
    
    -- Triguṇa scores (Phase 3)
    sattva REAL DEFAULT 0.33,
    rajas REAL DEFAULT 0.34,
    tamas REAL DEFAULT 0.33,
    state TEXT DEFAULT 'active',            -- active, in_flux, latent, dissolved
    
    -- Zvec reference
    embedding_id TEXT,                      -- Reference to Zvec document ID
    
    -- Timestamps
    created_at TEXT NOT NULL,               -- ISO 8601
    updated_at TEXT NOT NULL,               -- ISO 8601
    last_recalled_at TEXT,                  -- Last time this memory was returned in a recall
    recall_count INTEGER DEFAULT 0,         -- Total times recalled
    
    -- Dissolution trace (Phase 3)
    dissolved_at TEXT,                       -- When dissolved
    dissolved_reason TEXT,                   -- Why (superseded by X, contradicted by Y)
    superseded_by TEXT                       -- ID of memory that replaced this
);

-- Feedback / meta-vāsanās (Phase 5)
CREATE TABLE feedback (
    id TEXT PRIMARY KEY,
    memory_id TEXT,                          -- Which memory the feedback is about (nullable)
    feedback_type TEXT NOT NULL,             -- 'helpful', 'irrelevant', 'missing', 'correction'
    context TEXT,                            -- What the user was doing when they gave feedback
    details TEXT,                            -- Free-text feedback details
    created_at TEXT NOT NULL,
    FOREIGN KEY (memory_id) REFERENCES memories(id)
);

-- Buddhi determination log (for Adhyavasāya learning)
CREATE TABLE determinations (
    id TEXT PRIMARY KEY,
    input_text TEXT NOT NULL,                -- What was evaluated (row shape: README "Determination log and Jev shadow mode")
    determination TEXT NOT NULL,             -- JSON trace of the determination and its outcome
    feedback_id TEXT,                        -- If user later corrected this determination
    created_at TEXT NOT NULL,
    FOREIGN KEY (feedback_id) REFERENCES feedback(id)
);

-- Indexes
CREATE INDEX idx_memories_scope ON memories(scope);
CREATE INDEX idx_memories_state ON memories(state);
CREATE INDEX idx_memories_importance ON memories(importance);
CREATE INDEX idx_memories_created ON memories(created_at);
CREATE INDEX idx_memories_sattva ON memories(sattva);
```

---

## MCP Tool Definitions

### Phase 1 Tools

#### `remember`
Store a memory through the Antaḥkaraṇa pipeline.

```
Input:
  content: string (required) — The text to remember
  scope: string (optional) — Override Buddhi's scope inference
  importance: float (optional) — Override Buddhi's importance assessment
  source_agent: string (optional) — Identify which agent is storing this

Output:
  memory_id: string — The stored memory's ID
  scope: string — Where it was stored
  importance: float — Assigned importance
  consolidated: boolean — Whether it triggered consolidation with existing memories
  consolidated_with: string[] — IDs of memories it was consolidated with
```

#### `recall`
Retrieve relevant memories for a given context.

```
Input:
  query: string (required) — What to search for
  limit: integer (optional, default 5) — Max results
  scope: string (optional) — Restrict search to a scope subtree
  include_latent: boolean (optional, default false) — Include Tamas-predominant memories

Output:
  memories: array of:
    memory_id: string
    content: string
    scope: string
    importance: float
    score: float — Composite score (semantic + recency + importance + guṇa)
    state: string — active/in_flux/latent
    created_at: string
    last_recalled_at: string
```

#### `forget`
Transition memories to latent or dissolved state.

```
Input:
  scope: string (optional) — Target scope subtree
  memory_id: string (optional) — Specific memory to forget
  force_dissolve: boolean (optional, default false) — Skip latent, go straight to dissolved

Output:
  affected: integer — Number of memories affected
  transitioned_to: string — 'latent' or 'dissolved'
```

### Phase 2 Tools

#### `extract_and_remember`
Break raw text into atomic facts and store each one.

```
Input:
  content: string (required) — Raw text (could be long)
  source_agent: string (optional)

Output:
  facts_extracted: integer
  memories_stored: integer — May be less than extracted if consolidation merged some
  memory_ids: string[]
```

### Phase 3 Tools

#### `system_health`
Diagnose the memory system's guṇa distribution.

```
Input: (none)

Output:
  total_memories: integer
  by_state: {active: int, in_flux: int, latent: int, dissolved: int}
  avg_sattva: float
  avg_rajas: float  
  avg_tamas: float
  diagnosis: string — 'healthy', 'stagnating', 'churning', 'overloaded'
  recommendations: string[] — Actionable suggestions
```

#### `memory_tree`
Show the scope hierarchy.

```
Input:
  root: string (optional, default '/') — Starting scope

Output:
  tree: nested object with scope paths, record counts, and dominant guṇa per scope
```

### Phase 5 Tools

#### `feedback`
Provide feedback on a recall result or the system's behavior.

```
Input:
  memory_id: string (optional) — Specific memory to give feedback on
  feedback_type: string (required) — 'helpful', 'irrelevant', 'missing', 'correction'
  details: string (optional) — Explanation
  context: string (optional) — What you were working on

Output:
  feedback_id: string
  adhyavasaya_updated: boolean — Whether this triggered a Buddhi prompt update
```

---

## Buddhi Prompt Design (Phase 1 starting point)

The Buddhi determination prompt is the most critical piece. Here's the Phase 1 starting point. This will evolve through Adhyavasāya.

```yaml
# config/buddhi_prompt.yaml
system: |
  You are Buddhi — the determining faculty in the Antaḥkaraṇa memory system.
  Your role is to evaluate incoming information and make storage determinations.
  
  For each input, determine:
  1. IMPORTANCE (0.0 to 1.0):
     - 0.0-0.2: Trivial, ephemeral (one-off commands, transient context)
     - 0.3-0.5: Moderately useful (task context, temporary decisions)
     - 0.6-0.8: Important (project decisions, learned patterns, preferences)
     - 0.9-1.0: Critical (architectural decisions, identity-level facts, foundational knowledge)
  
  2. SCOPE (hierarchical path):
     - Suggest a path like /project/name/aspect or /personal/preference
     - Use existing scopes when content fits; create new ones when needed
     - Keep depth to 2-3 levels maximum
  
  3. CATEGORIES (array of strings):
     - Tag with relevant categories (architecture, decision, preference, debug, etc.)
  
  4. STORE_DECISION (boolean):
     - Should this be stored at all? Some inputs are too trivial or transient.
  
  Respond ONLY with valid JSON, no preamble:
  {"importance": 0.7, "scope": "/project/jozu/architecture", "categories": ["architecture", "decision"], "store": true}

# Appended dynamically by Adhyavasāya (Phase 5):
learned_guidelines: []
```

---

## Guṇa Scoring Rules (Phase 3)

### Initial Assignment (at encoding time)
New memories enter with:
- `sattva`: Based on Buddhi's confidence in its determination (high confidence = high sattva)
- `rajas`: 0.4 (new memories are active/unsettled)
- `tamas`: 0.1 (fresh memories resist dormancy)
- Normalize so all three sum to 1.0

### Lifecycle Updates

| Event | Sattva | Rajas | Tamas |
|-------|--------|-------|-------|
| Memory recalled and used | +0.1 | — | -0.1 |
| Memory recalled but not used | — | — | +0.05 |
| User feedback: "helpful" | +0.15 | -0.05 | -0.1 |
| User feedback: "irrelevant" | -0.1 | +0.05 | +0.05 |
| Consolidation (merged/updated) | — | +0.15 | -0.05 |
| Contradiction detected | -0.1 | +0.2 | -0.1 |
| Time decay (per day, no recall) | -0.005 | -0.005 | +0.01 |
| Reactivated from latent | +0.2 | +0.1 | -0.3 |

After each update, normalize to sum to 1.0 and clamp each to [0.05, 0.9].

### State Derivation
- **Active**: sattva >= rajas AND sattva >= tamas
- **In Flux**: rajas > sattva AND rajas > tamas
- **Latent**: tamas >= 0.5
- **Dissolved**: manually triggered by Buddhi after confirming supersession

---

## Ahamkāra Config Format (Phase 4)

```yaml
# config/ahamkara.yaml
name: "Mike"
role: "Web developer and SaaS builder"
context: |
  Self-employed, running Sonic Pixel in Japan.
  Primary client: Friendly Fires (Canadian fireplace/BBQ parts retailer).
  Building SaaS products for English-speaking expats in Japan (Jozu, KantanHealth).
  Uses Claude Code, OpenClaw, Gemini for different workflows.

active_projects:
  - name: "Jozu"
    scope: "/project/jozu"
    description: "AI-powered document translation app for Japan expats"
  - name: "Friendly Fires"
    scope: "/project/friendly-fires"
    description: "WooCommerce/Shopify fireplace parts retailer"
  - name: "Antahkarana"
    scope: "/project/antahkarana"
    description: "This memory system itself"

preferences:
  communication_style: "Direct, concise, technical"
  values: ["simplicity", "portability", "vedic_philosophy"]
  
boundaries:
  - "Do not store sensitive credentials or API keys"
  - "Do not store personal health information"
```

---

## Environment Setup

```bash
# Create project
mkdir antahkarana && cd antahkarana
python -m venv .venv
source .venv/bin/activate

# Dependencies
pip install mcp zvec google-generativeai pyyaml

# Environment
cp .env.example .env
# Edit .env with GEMINI_API_KEY
```

### .env.example
```
GEMINI_API_KEY=your_key_here
ANTAHKARANA_DATA_DIR=./data
ANTAHKARANA_CONFIG_DIR=./config
```

---

## MCP Client Configuration

### Claude Code (~/.claude/claude_code_config.json)
```json
{
  "mcpServers": {
    "antahkarana": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/antahkarana",
      "env": {
        "GEMINI_API_KEY": "your_key_here"
      }
    }
  }
}
```

### OpenClaw
Add as an MCP tool source pointing to the same server.

---

## Testing Strategy

### Phase 1 Tests
1. **Store and retrieve**: Remember "We decided to use PostgreSQL", recall "What database?", verify match.
2. **Scope inference**: Store several project-related memories, verify Buddhi assigns reasonable scopes.
3. **Importance scoring**: Store a trivial debug log and an architecture decision, verify different importance scores.
4. **Embedding quality**: Store similar memories, verify semantic search returns them for related queries.

### Phase 3 Tests
1. **Guṇa drift**: Store a memory, simulate no recall for 30 days, verify Tamas increases and state transitions to Latent.
2. **Reactivation**: Query a latent memory with `include_latent=true`, verify guṇa rebalances toward Active.
3. **System health**: Populate with mixed memories, verify diagnosis matches expected state.

### Phase 5 Tests
1. **Feedback loop**: Give negative feedback on irrelevant recall results, verify Buddhi adjusts behavior on subsequent stores.
2. **Meta-vāsanā accumulation**: Provide 10+ feedback items, verify Buddhi prompt is augmented with learned patterns.

---

## Key Principles

1. **Buddhi before Chitta**: Nothing enters storage without passing through the determination layer.
2. **Guṇas are dynamic**: Every memory's scores evolve continuously based on lifecycle events.
3. **Identity colors everything**: Ahamkāra preferences influence every determination Buddhi makes.
4. **Learn from mistakes**: The Adhyavasāya loop ensures the system improves with use.
5. **Platform agnostic**: The system knows nothing about which agent is calling it. It serves Puruṣa, not any particular body.
6. **Start simple, grow smart**: Phase 1 is intentionally basic. Intelligence layers on incrementally.

---

## Notes for Claude Code

- Start with Phase 1 only. Get remember/recall working end-to-end before adding complexity.
- The Buddhi prompt is the hardest part. Expect to iterate on it.
- Use Gemini's free embedding tier (`models/text-embedding-004`) to avoid API costs.
- Zvec is Python-only, `pip install zvec`. Check compatibility with Python 3.12.
- SQLite is stdlib, no extra dependency needed.
- MCP Python SDK: `pip install mcp`. Use stdio transport for Claude Code compatibility.
- The whitepaper (`antahkarana-whitepaper.docx`) contains the full philosophical framework. Refer to it for architectural decisions.

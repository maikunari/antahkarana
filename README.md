# Antaḥkaraṇa

A platform-agnostic persistent memory layer for AI agents, built as a standalone MCP server. Plug it into Claude Code, OpenClaw, Cowork, or any MCP-compatible client — your knowledge persists across every tool you use. The architecture is grounded in the Vedic Antaḥkaraṇa (inner instruments of mind) framework: Buddhi (an open model on OpenRouter, DeepSeek V4.1 Flash by default) evaluates every input before Chitta (Zvec + SQLite) stores it, so memory is discriminated, not just accumulated.

## Quick Start

```bash
cd antahkarana
python3.12 -m venv .venv
source .venv/bin/activate
pip install "mcp<2" zvec "fastembed>=0.8.1,<0.9" google-re2 pyyaml python-dotenv
```

Create `.env`:

```
OPENROUTER_API_KEY=your_key_here
# Optional: the OpenRouter model id Buddhi asks (default deepseek/deepseek-v4.1-flash)
ANTAHKARANA_BUDDHI_MODEL=
# Optional: Jev shadow judge (see "Determination log and Jev shadow mode")
TYPESAFE_API_KEY=
```

Buddhi sends the (scrubbed) memory text to OpenRouter's chat completions API with a strict JSON schema, so `OPENROUTER_API_KEY` is the only key it needs. Embeddings run locally: the pinned `nomic-ai/nomic-embed-text-v1.5` model (768 dims, Apache-2.0, ONNX Runtime via fastembed) needs no key, and no text leaves the machine to be embedded. The first `remember` or `recall` downloads the model files (about 550 MB) into the Hugging Face cache; after that it works offline.

Run the server directly:

```bash
python -m src
```

Run the tests (no network or API keys needed):

```bash
pip install pytest
python -m pytest
```

Live checks are opt-in: they run only with `OPENROUTER_API_KEY` (Buddhi), `TYPESAFE_API_KEY` (Jev) or `ANTAHKARANA_LIVE_EMBEDDINGS=1` (downloads the embedding model) set.

## Connecting to Claude Code

Register the server with `claude mcp add`. It has no working-directory setting, so give the install's `.env` absolute paths (`ANTAHKARANA_DATA_DIR=/path/to/antahkarana/data`, `ANTAHKARANA_CONFIG_DIR=/path/to/antahkarana/config`) and set `PYTHONPATH` so `python -m src` imports from any directory. The server reads `.env` from the install directory wherever it is started, so the keys stay there.

```bash
claude mcp add --scope user antahkarana \
  -e PYTHONPATH=/path/to/antahkarana \
  -- /path/to/antahkarana/.venv/bin/python -m src
```

Check it with `claude mcp get antahkarana`, or `/mcp` in a session.

Under stdio each Claude Code session starts its own server, and the Zvec vector store allows one open writer, so a second concurrent session fails to connect. To use Antaḥkaraṇa from several sessions at once, run the shared server below instead.

## Running a shared server

Set `ANTAHKARANA_TRANSPORT=http` and the server runs once over MCP streamable HTTP at `http://127.0.0.1:ANTAHKARANA_PORT/mcp` (default port `8799`); every client on the machine connects to that one process. stdio stays the default.

```bash
ANTAHKARANA_TRANSPORT=http ANTAHKARANA_PORT=8799 python -m src
```

To keep it running, install it as a systemd user service. [`contrib/antahkarana.service`](contrib/antahkarana.service) is an example for an install at `~/.local/share/antahkarana/app`; edit its paths and port, then:

```bash
cp contrib/antahkarana.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now antahkarana
journalctl --user -u antahkarana -f   # logs
```

Then register Claude Code against the URL instead of the command (remove a stdio registration first with `claude mcp remove antahkarana -s user`):

```bash
claude mcp add --scope user --transport http antahkarana http://127.0.0.1:8799/mcp
```

The HTTP endpoint has no authentication: any process on the machine that can reach the port can read and write memories. It always binds `127.0.0.1`, so nothing off the machine can reach it. Stop the service before running `python -m src.dvarapala audit` or `purge`, which need the store to themselves.

## Connecting to OpenClaw

Add as an MCP tool source: point your MCP client at the same stdio command, or at the shared server's URL (see "Running a shared server"):

```
command: /path/to/antahkarana/.venv/bin/python
args: ["-m", "src"]
cwd: /path/to/antahkarana
```

Any MCP-compatible client can connect the same way. A client with no `cwd` setting needs the absolute `.env` paths and `PYTHONPATH` described for Claude Code.

## Tools

### `remember`

Store a memory through the Buddhi evaluation pipeline.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | yes | The text to remember |
| `scope` | string | no | Override Buddhi's scope inference (e.g. `/project/jozu/architecture`) |
| `importance` | float | no | Override Buddhi's importance assessment (0.0–1.0) |
| `source_agent` | string | no | Which agent is storing this (`claude-code`, `openclaw`, etc.) |

Returns: `memory_id`, `scope`, `importance`, `categories`, or `stored: false` if Buddhi determines the content is too trivial. If Buddhi's model call fails (no key, network, HTTP error, timeout, or an answer that does not match the schema exactly), nothing is stored and the result is `stored: false` with `reason: "buddhi_error"` and a `note` saying why. Secrets are removed from every input first (see "Secrets keeper"): when any were, the result adds `redactions` (field, kind and count, never the value) and a `note`. Content that is nothing but a secret returns `stored: false` with `reason: "secret_only"` and reaches no model.

### `recall`

Retrieve relevant memories via semantic search with composite scoring.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | yes | What to search for |
| `limit` | int | no | Max results (default 5) |
| `scope` | string | no | Restrict to a scope subtree |
| `include_latent` | bool | no | Include dormant memories (default false) |

Returns: Ranked list of memories with `content`, `scope`, `importance`, `score`, `state`. A secret in the query is removed before it is embedded; the result then echoes the scrubbed query and adds `redactions` (field, kind and count, never the value).

Scoring: `0.6 * semantic_similarity + 0.2 * importance + 0.2 * recency` (30-day half-life exponential decay).

### `forget`

Transition memories to latent (dormant) or dissolved (trace only) state.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `memory_id` | string | no* | Specific memory to forget |
| `scope` | string | no* | Target all memories in this scope subtree |
| `force_dissolve` | bool | no | Skip latent, go straight to dissolved (default false) |

\* At least one of `memory_id` or `scope` is required.

Latent keeps the memory's text and vector, since it is reversible. Dissolved purges them: the content becomes `[dissolved]` (the row keeps its id, scope, categories and dates as the trace), the vector is deleted, the linked `determinations` rows lose their `input_text`, and linked `feedback` text is cleared. SQLite runs with `secure_delete` and the WAL is truncated. Zvec only hides a deleted vector until the collection is rebuilt, which `python -m src.dvarapala purge` does.

## Secrets keeper (Dvārapāla)

`src/dvarapala/` keeps API keys, tokens, passwords and other credentials out of Antaḥkaraṇa. It runs first in `remember` and `recall`, before Buddhi, Jev, the embedder or Chitta see anything, and replaces each secret with a typed placeholder such as `[secret:stripe-access-token]`. The rest of the memory is still stored. The value is never stored, logged, returned or sent to a model.

- **Detection is local.** gitleaks' default rules (`src/dvarapala/gitleaks.toml`, v8.30.1, MIT, compiled with RE2), an OpenRouter key rule (gitleaks has none), three rules for secrets written in prose (`password is …`, `login … is user / pass`, passwords in URLs), and an entropy backstop for long random-looking tokens.
- **Where it applies.** `remember` content, the `scope` and `source_agent` overrides (a secret there drops the override), the `recall` query, and Buddhi's own `scope` and `categories` in case the model echoes a secret. The whole determination row is scrubbed before it is logged.
- **Fails closed.** If the keeper cannot load or run, `remember` and `recall` refuse and nothing is sent anywhere. The server does not start without it.
- **Write guard.** Chitta checks every text it writes and raises `SecretInWrite` instead of storing a secret, so a future write path that forgets to scrub fails loudly.
- **False positives.** A value that is not a secret can be allowed in `config/dvarapala.yaml`. There is deliberately no per-call override.
- **Keep a pointer, not the value.** "The FF Stripe key is in 1Password under 'FF Stripe live'" is stored as written.

Secrets stored before the keeper existed can be found and removed. Stop the server first:

```bash
python -m src.dvarapala audit   # read-only: counts by table, column and kind, row ids; never values
python -m src.dvarapala purge   # scrub, re-embed scrubbed text, dissolve secret-only memories,
                                # purge old dissolved rows, VACUUM, rebuild vectors, verify
```

`purge` re-embeds scrubbed memories that stay active with the local embedding model; if the model cannot load, it changes nothing. Neither command can reach backups or snapshots of `data/`, or text already sent to Buddhi's model or Jev, so rotate every credential the audit lists.

It does not protect against a secret that is already in the calling agent's context, its model provider or its transcript before `remember` runs; secrets described in words or split across calls; or personal health information, which is not a pattern. Not built yet: keeping content out of debug logs, a Jev secret check on scrubbed text once Jev decides, and an optional vault.

## Determination log and Jev shadow mode

Every `remember` call writes one row to the `determinations` table in `chitta.db`: the scrubbed input text in `input_text`, the stored memory's ID in `memory_id`, and a JSON `determination` holding Buddhi's answer under `buddhi` (`provider`, the requested `model`, the served `model_version`, `served_by`, `latency_ms`, `status` and the raw JSON `response`, or the `error` when the call failed), the Jev shadow answer, `decided_by`, the `redactions` the secrets keeper made, the `source_agent`, and the `final` outcome (stored or not, with the memory ID, scope, importance and categories after caller overrides). The whole row is scrubbed before it is written. `decided_by` is `"buddhi"`, or `"dvarapala"` for content refused as nothing but a secret, which is logged with no model answers. A logging failure never fails `remember`.

A refused input is logged as `[redacted: likely secret]` instead of its text when Jev's secret probability is at or above `SECRET_THRESHOLD`, or when Jev gave no answer (key unset, error or timeout), since then there is no secret signal. Stored inputs are logged with their scrubbed text.

With `TYPESAFE_API_KEY` set, Buddhi also asks TypeSafe's Jev (`src/buddhi/jev.py`, pinned to `jev-1.13.0`) the keep-or-discard question, in parallel with Buddhi's model. Jev sees only the memory text. Its answer (kind, per-kind probabilities, keep probability, secret probability, would-store) is logged, and **Buddhi's `store` still decides**. Any Jev error, or no answer within 3 s of the call starting, is logged as `error` or `timeout` and never changes whether the memory is stored. Without the key, Jev is off.

Inspect disagreements:

```bash
sqlite3 data/chitta.db "SELECT input_text, determination FROM determinations
  WHERE json_extract(determination, '$.jev.status') = 'ok'
    AND json_extract(determination, '$.jev.store') != json_extract(determination, '$.buddhi.response.store')"
```

## Project Structure

```
antahkarana/
├── config/
│   ├── buddhi_prompt.yaml      # Buddhi determination prompt
│   ├── dvarapala.yaml          # Secrets keeper allowlist
│   └── ahamkara.yaml           # Identity config (Phase 4)
├── src/
│   ├── server.py               # MCP server entry point (Prāṇa)
│   ├── transport.py            # stdio or shared streamable-HTTP settings
│   ├── dvarapala/
│   │   ├── keeper.py           # Secrets keeper: detect and scrub
│   │   ├── audit.py            # Find and purge secrets already stored
│   │   └── gitleaks.toml       # Vendored gitleaks rules (MIT, GITLEAKS_LICENSE)
│   ├── chitta/
│   │   ├── models.py           # MemoryRecord, RecallResult dataclasses
│   │   ├── schema.py           # SQLite DDL + init
│   │   └── store.py            # Zvec + SQLite unified store
│   ├── buddhi/
│   │   ├── engine.py           # Buddhi determination via OpenRouter
│   │   ├── prompts.py          # Prompt loading from YAML
│   │   ├── jev.py              # Jev keep-or-discard judge (shadow mode)
│   │   └── embeddings.py       # Local embedding model (768-dim)
│   ├── manas/
│   │   └── tools.py            # remember, recall, forget logic
│   ├── guna/
│   │   └── engine.py           # stub (Phase 3)
│   ├── ahamkara/
│   │   └── identity.py         # stub (Phase 4)
│   └── adhyavasaya/
│       └── feedback.py         # stub (Phase 5)
├── contrib/
│   └── antahkarana.service     # Example systemd user unit for the shared server
├── tests/                      # pytest; fixtures/buddhi_examples.yaml holds kept/refused examples
└── data/                       # Runtime data (gitignored)
    ├── chitta.db               # SQLite
    └── chitta_vectors/         # Zvec collection
```

## Phases

**Phase 1 — Core Loop (current)**
Remember + recall + forget. Buddhi evaluates importance/scope/categories via an open model on OpenRouter. Chitta stores in Zvec (semantic vectors) + SQLite (metadata) with dual-write transactional safety.

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
| Reasoning (Buddhi) | DeepSeek V4.1 Flash (`deepseek/deepseek-v4.1-flash`) on OpenRouter; `ANTAHKARANA_BUDDHI_MODEL` overrides |
| Keep-or-discard shadow judge | TypeSafe Jev (`jev-1.13.0`), optional |
| Embeddings | `nomic-ai/nomic-embed-text-v1.5` @ 768 dims, local via fastembed (ONNX Runtime), pinned revision |
| Vector store (Chitta) | Zvec |
| Structured store | SQLite |
| MCP framework | `mcp` Python SDK (FastMCP) |
| Transport | stdio (default) or streamable HTTP (`ANTAHKARANA_TRANSPORT=http`) |

# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

- Tests: `python -m pytest` from the repo root (config in `pyproject.toml`). They need no network or API keys; `tests/conftest.py` fakes the OpenRouter and Jev transports and the embedder, and the forget/purge tests use a real Zvec collection in a temp dir. Install `mcp<2`: mcp 2.x removed the `FastMCP` import `src/server.py` uses.
- Buddhi's keep-or-discard call: the OpenRouter model's `store` is authoritative (`src/buddhi/engine.py`; any model failure is a refusal, never a store). Jev (`src/buddhi/jev.py`) runs in shadow mode only and is logged, never acted on. Every determination is logged to the `determinations` table; the README section "Determination log and Jev shadow mode" describes the row shape.
- Embeddings are local (`src/buddhi/embeddings.py`, fastembed/ONNX, model pinned by HF revision); the Zvec collection is fixed at 768 dims, so a model swap needs a 768-dim model or a re-embed.
- Secrets (`OPENROUTER_API_KEY`, optional `TYPESAFE_API_KEY`) come from the environment or the gitignored `.env`; see `.env.example`.
- Secrets keeper (`src/dvarapala/`): all caller text is scrubbed before any model call or write, and `ChittaStore` refuses writes that still hold a secret (`SecretInWrite`). Any new write path must pass scrubbed text. Test secrets are generated at run time (`tests/secret_samples.py`); never commit a realistic key.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.

"""Prāṇa — the MCP server entry point for Antaḥkaraṇa.

The lifecycle manager that binds all components together.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from src.buddhi.embeddings import EmbeddingEngine
from src.buddhi.engine import BuddhiEngine
from src.buddhi.jev import JevClient
from src.chitta.store import ChittaStore
from src.dvarapala.keeper import Keeper
from src.manas import tools
from src.transport import HOST, load_transport_settings

# Load environment from the repo's .env whatever the working directory, so Claude Code
# and a service manager can start the server from anywhere. Real environment wins.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("antahkarana")

# Configuration
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
# Optional: enables the Jev shadow judge. Absent means off; Buddhi decides either way.
TYPESAFE_API_KEY = os.environ.get("TYPESAFE_API_KEY", "")
DATA_DIR = os.environ.get("ANTAHKARANA_DATA_DIR", "./data")
CONFIG_DIR = os.environ.get("ANTAHKARANA_CONFIG_DIR", "./config")
# Read before anything opens the store, so a bad setting fails fast.
TRANSPORT = load_transport_settings(os.environ)

# Initialize components. The secrets keeper loads first: without it nothing starts.
keeper = Keeper.load(CONFIG_DIR)
logger.info("Secrets keeper: %d rules", keeper.rule_count)
chitta = ChittaStore(data_dir=DATA_DIR, keeper=keeper)
chitta.init()

embeddings = EmbeddingEngine()
jev = JevClient(api_key=TYPESAFE_API_KEY) if TYPESAFE_API_KEY else None
logger.info("Jev shadow judge: %s", f"on ({jev.model})" if jev else "off")
buddhi = BuddhiEngine(api_key=OPENROUTER_API_KEY, config_dir=CONFIG_DIR, jev=jev)
if not OPENROUTER_API_KEY:
    logger.warning("OPENROUTER_API_KEY is not set: Buddhi will refuse every remember")
logger.info("Buddhi model: %s", buddhi.model)

# Create MCP server. Host and port go in explicitly: FastMCP's own FASTMCP_HOST/FASTMCP_PORT
# settings are overridden by its constructor defaults. Passing them here (not after) also
# gives the localhost host FastMCP's DNS rebinding protection.
mcp = FastMCP("antahkarana", host=HOST, port=TRANSPORT.port)


@mcp.tool()
def remember(
    content: str,
    scope: str | None = None,
    importance: float | None = None,
    source_agent: str | None = None,
) -> str:
    """Store a memory through the Antaḥkaraṇa pipeline.

    Buddhi evaluates the content for importance, scope, and categories
    before storing in Chitta. Use this to persist knowledge, decisions,
    preferences, or any information worth remembering across sessions.

    Args:
        content: The text to remember
        scope: Override Buddhi's scope inference (e.g. /project/jozu/architecture)
        importance: Override Buddhi's importance assessment (0.0 to 1.0)
        source_agent: Identify which agent is storing this (claude-code, openclaw, etc.)
    """
    result = tools.remember(
        content,
        chitta=chitta,
        buddhi=buddhi,
        embeddings=embeddings,
        scope=scope,
        importance=importance,
        source_agent=source_agent,
        keeper=keeper,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def recall(
    query: str,
    limit: int = 5,
    scope: str | None = None,
    include_latent: bool = False,
) -> str:
    """Retrieve relevant memories for a given context.

    Performs semantic search across all stored memories and returns
    composite-scored results blending similarity, importance, and recency.

    Args:
        query: What to search for
        limit: Maximum number of results (default 5)
        scope: Restrict search to a scope subtree (e.g. /project/jozu)
        include_latent: Include dormant memories in results (default false)
    """
    result = tools.recall(
        query,
        chitta=chitta,
        embeddings=embeddings,
        limit=limit,
        scope=scope,
        include_latent=include_latent,
        keeper=keeper,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def forget(
    memory_id: str | None = None,
    scope: str | None = None,
    force_dissolve: bool = False,
) -> str:
    """Transition memories to latent or dissolved state.

    Latent memories are dormant but recoverable. Dissolved memories
    leave only a trace record. Target by specific memory ID or by
    scope subtree.

    Args:
        memory_id: Specific memory to forget
        scope: Target all memories in this scope subtree
        force_dissolve: Skip latent, go straight to dissolved (default false)
    """
    result = tools.forget(
        chitta=chitta,
        memory_id=memory_id,
        scope=scope,
        force_dissolve=force_dissolve,
    )
    return json.dumps(result, indent=2)


def main() -> None:
    """Run the Antaḥkaraṇa MCP server."""
    if TRANSPORT.transport == "http":
        logger.info(
            "Starting Antaḥkaraṇa memory server on http://%s:%d%s",
            HOST,
            TRANSPORT.port,
            mcp.settings.streamable_http_path,
        )
        mcp.run("streamable-http")
    else:
        logger.info("Starting Antaḥkaraṇa memory server...")
        mcp.run()


if __name__ == "__main__":
    main()

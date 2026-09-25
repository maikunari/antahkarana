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
from src.manas import tools

# Load environment
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("antahkarana")

# Configuration
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# Optional: enables the Jev shadow judge. Absent means off; Gemini decides either way.
TYPESAFE_API_KEY = os.environ.get("TYPESAFE_API_KEY", "")
DATA_DIR = os.environ.get("ANTAHKARANA_DATA_DIR", "./data")
CONFIG_DIR = os.environ.get("ANTAHKARANA_CONFIG_DIR", "./config")

# Initialize components
chitta = ChittaStore(data_dir=DATA_DIR)
chitta.init()

embeddings = EmbeddingEngine(api_key=GEMINI_API_KEY)
jev = JevClient(api_key=TYPESAFE_API_KEY) if TYPESAFE_API_KEY else None
logger.info("Jev shadow judge: %s", f"on ({jev.model})" if jev else "off")
buddhi = BuddhiEngine(api_key=GEMINI_API_KEY, config_dir=CONFIG_DIR, jev=jev)

# Create MCP server
mcp = FastMCP("antahkarana")


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
    logger.info("Starting Antaḥkaraṇa memory server...")
    mcp.run()


if __name__ == "__main__":
    main()

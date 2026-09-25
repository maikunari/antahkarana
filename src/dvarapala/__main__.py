"""Command line: `python -m src.dvarapala audit|purge`.

Stop the MCP server first: purge rewrites the database and rebuilds the
vector index, and must be the only writer while it runs.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.buddhi.embeddings import EmbeddingEngine
from src.dvarapala.audit import EmbedderRequired, audit, purge
from src.dvarapala.keeper import Keeper


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        prog="python -m src.dvarapala",
        description="Find (audit) or remove (purge) secrets already stored in Chitta. "
        "Never prints a secret value.",
    )
    parser.add_argument("command", choices=["audit", "purge"])
    parser.add_argument(
        "--data-dir", default=os.environ.get("ANTAHKARANA_DATA_DIR", "./data"), type=Path
    )
    parser.add_argument(
        "--config-dir", default=os.environ.get("ANTAHKARANA_CONFIG_DIR", "./config"), type=Path
    )
    args = parser.parse_args(argv)

    db_path = args.data_dir / "chitta.db"
    if not db_path.exists():
        print(f"No database at {db_path}; nothing to {args.command}.")
        return 0
    keeper = Keeper.load(args.config_dir)

    if args.command == "audit":
        report = audit(db_path, keeper)
        print("\n".join(report.lines()))
        if not report.clean:
            print("Run `python -m src.dvarapala purge` with the server stopped to remove them.")
        return 0 if report.clean else 1

    # Loaded before any write, so a model that cannot load changes nothing.
    embeddings = EmbeddingEngine()
    try:
        embeddings.load()
    except Exception as err:
        print(f"Nothing changed: could not load the embedding model: {type(err).__name__}: {err}")
        return 2
    try:
        before, after, files = purge(args.data_dir, keeper, embeddings.embed)
    except EmbedderRequired as err:
        print(f"Nothing changed: {err}")
        return 2
    print("Before:")
    print("\n".join("  " + line for line in before.lines()))
    print("After:")
    print("\n".join("  " + line for line in after.lines()))
    print(f"Data files still holding a removed value: {files}")
    print(
        "Backups and snapshots of the data directory still hold the old values; "
        "the keeper cannot reach them."
    )
    return 0 if after.clean and files == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

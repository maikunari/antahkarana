"""Which MCP transport the server runs: stdio (the default) or one shared streamable-HTTP server.

Under stdio every client starts its own server, and Zvec's exclusive lock on the vector
store lets only one of them run at a time. The HTTP transport runs one long-lived server
that any number of clients on the machine connect to.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

TRANSPORTS = ("stdio", "http")
HOST = "127.0.0.1"
# Not 8000: FastMCP's default, and commonly taken.
DEFAULT_PORT = 8799


@dataclass(frozen=True)
class TransportSettings:
    transport: str = "stdio"
    port: int = DEFAULT_PORT


def load_transport_settings(environ: Mapping[str, str]) -> TransportSettings:
    """Read ANTAHKARANA_TRANSPORT and ANTAHKARANA_PORT; unset or empty means default.

    Raises ValueError on an unknown transport or a port that is not 1-65535, so a typo
    stops the server at startup instead of silently falling back to stdio.
    """
    transport = environ.get("ANTAHKARANA_TRANSPORT") or "stdio"
    if transport not in TRANSPORTS:
        raise ValueError(
            f"ANTAHKARANA_TRANSPORT must be one of {', '.join(TRANSPORTS)}, not {transport!r}"
        )
    if transport == "stdio":
        return TransportSettings()

    raw_port = (environ.get("ANTAHKARANA_PORT") or "").strip()
    if not raw_port:
        return TransportSettings(transport)
    try:
        port = int(raw_port)
    except ValueError:
        port = 0
    if not 1 <= port <= 65535:
        raise ValueError(f"ANTAHKARANA_PORT must be a port number (1-65535), not {raw_port!r}")
    return TransportSettings(transport, port)

"""Transport settings, and one shared streamable-HTTP server serving concurrent clients."""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from src.transport import DEFAULT_PORT, TransportSettings, load_transport_settings

ROOT = Path(__file__).resolve().parent.parent


def test_default_is_stdio():
    assert load_transport_settings({}) == TransportSettings("stdio", DEFAULT_PORT)


def test_empty_values_mean_default():
    env = {"ANTAHKARANA_TRANSPORT": "", "ANTAHKARANA_PORT": ""}
    assert load_transport_settings(env).transport == "stdio"


def test_stdio_ignores_port():
    env = {"ANTAHKARANA_TRANSPORT": "stdio", "ANTAHKARANA_PORT": "not-a-port"}
    assert load_transport_settings(env) == TransportSettings()


def test_http_default_port():
    settings = load_transport_settings({"ANTAHKARANA_TRANSPORT": "http"})
    assert settings == TransportSettings("http", DEFAULT_PORT)


def test_http_port():
    env = {"ANTAHKARANA_TRANSPORT": "http", "ANTAHKARANA_PORT": "9123"}
    assert load_transport_settings(env) == TransportSettings("http", 9123)


@pytest.mark.parametrize("port", ["abc", "0", "65536", "-1", "80.5"])
def test_bad_port_refused(port):
    env = {"ANTAHKARANA_TRANSPORT": "http", "ANTAHKARANA_PORT": port}
    with pytest.raises(ValueError, match="ANTAHKARANA_PORT"):
        load_transport_settings(env)


@pytest.mark.parametrize("transport", ["sse", "HTTP", "Http", " http", "http ", "STDIO"])
def test_unknown_transport_refused(transport):
    with pytest.raises(ValueError, match="ANTAHKARANA_TRANSPORT"):
        load_transport_settings({"ANTAHKARANA_TRANSPORT": transport})


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_port(proc: subprocess.Popen, port: int, log: Path, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise AssertionError(f"server exited early:\n{log.read_text()}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.2)
    raise AssertionError(f"server did not listen on {port} within {timeout}s")


async def _initialize_and_list_tools(url: str) -> list[str]:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async with streamable_http_client(url) as (read, write, _session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return sorted(tool.name for tool in result.tools)


async def _two_clients(url: str) -> list[list[str]]:
    return await asyncio.gather(_initialize_and_list_tools(url), _initialize_and_list_tools(url))


def test_two_concurrent_clients_share_one_http_server(tmp_path):
    """The real entry point (`python -m src`) over HTTP, with a real Zvec store, no keys."""
    port = _free_port()
    env = {
        **os.environ,
        "ANTAHKARANA_TRANSPORT": "http",
        "ANTAHKARANA_PORT": str(port),
        "ANTAHKARANA_DATA_DIR": str(tmp_path / "data"),
        "ANTAHKARANA_CONFIG_DIR": str(ROOT / "config"),
        # Set but empty, so a developer's .env cannot switch on a model call.
        "OPENROUTER_API_KEY": "",
        "TYPESAFE_API_KEY": "",
        "PYTHONPATH": str(ROOT),
    }
    # Run from elsewhere to show the server does not depend on the working directory.
    log = tmp_path / "server.log"
    with open(log, "w") as out:
        proc = subprocess.Popen(
            [sys.executable, "-m", "src"],
            cwd=tmp_path,
            env=env,
            stdout=out,
            stderr=subprocess.STDOUT,
        )
    try:
        _wait_for_port(proc, port, log)
        results = asyncio.run(
            asyncio.wait_for(_two_clients(f"http://127.0.0.1:{port}/mcp"), timeout=30)
        )
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    assert results == [["forget", "recall", "remember"]] * 2

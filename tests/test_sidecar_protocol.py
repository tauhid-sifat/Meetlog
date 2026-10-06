"""Integration tests for the sidecar TCP protocol.

These spawn the sidecar as a real subprocess and speak its wire protocol, so
they verify the startup contract (port on stdout) that the Rust parent relies
on. They do not require a Gemini API key.

Subprocess spawning uses the sync ``subprocess`` module to avoid the Windows
asyncio-proactor teardown warning; only the socket side is async.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path


def _spawn(meetings_dir: Path) -> tuple[subprocess.Popen, int]:
    env = dict(os.environ)
    env.pop("GEMINI_API_KEY", None)  # force the no-key path
    env["MEETLOG_MEETINGS_DIR"] = str(meetings_dir)
    proc = subprocess.Popen(
        [sys.executable, "-m", "ai.main"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
    )
    assert proc.stdout is not None
    port = int(proc.stdout.readline().strip())
    return proc, port


def _shutdown(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
    for stream in (proc.stdout, proc.stderr):
        if stream is not None:
            stream.close()


def _roundtrip(port: int, message: dict) -> dict:
    async def scenario() -> dict:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        try:
            writer.write((json.dumps(message) + "\n").encode())
            await writer.drain()
            line = await asyncio.wait_for(reader.readline(), timeout=5)
            return json.loads(line.decode())
        finally:
            writer.close()
            await writer.wait_closed()

    return asyncio.run(scenario())


def test_sidecar_prints_port_and_answers_ping(tmp_path):
    proc, port = _spawn(tmp_path)
    try:
        assert 0 < port < 65536
        assert _roundtrip(port, {"type": "ping"})["type"] == "pong"
    finally:
        _shutdown(proc)


def test_sidecar_reports_missing_api_key(tmp_path):
    proc, port = _spawn(tmp_path)
    try:
        payload = _roundtrip(port, {"type": "start", "config": {}})
        assert payload["type"] == "error"
        assert "API key" in payload["message"]
    finally:
        _shutdown(proc)

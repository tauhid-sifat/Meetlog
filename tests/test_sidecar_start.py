"""Regression: a start with no model must fall back to the default model.

Previously the UI sent `"model": null`, and `config.get("model", default)`
returned None, so the provider raised "model is required." and the session
never opened.
"""

from __future__ import annotations

import asyncio
import json
import os

import pytest

from tests.test_sidecar_protocol import _shutdown, _spawn


@pytest.mark.skipif(not os.environ.get("GEMINI_API_KEY"), reason="needs GEMINI_API_KEY")
def test_start_without_model_uses_default(tmp_path):
    async def scenario(port: int) -> dict:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        try:
            writer.write(
                (json.dumps({"type": "start", "config": {"api_key": os.environ["GEMINI_API_KEY"]}}) + "\n").encode()
            )
            await writer.drain()
            for _ in range(30):
                line = await asyncio.wait_for(reader.readline(), timeout=25)
                payload = json.loads(line.decode())
                if payload["type"] in ("ready", "error"):
                    return payload
            return {}
        finally:
            writer.close()
            await writer.wait_closed()

    proc, port = _spawn(tmp_path)
    try:
        result = asyncio.run(scenario(port))
        assert result["type"] == "ready", f"expected ready, got {result}"
    finally:
        _shutdown(proc)

"""Verify the sidecar receives and accounts for audio chunks over TCP."""

from __future__ import annotations

import asyncio
import base64
import json

from tests.test_sidecar_protocol import _shutdown, _spawn


def test_sidecar_counts_audio_chunks(tmp_path):
    async def scenario(port: int) -> dict:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        try:
            pcm = b"\x01\x02" * 1600  # 100 ms of 16 kHz mono i16
            for i in range(5):
                source = "mic" if i % 2 == 0 else "system"
                message = {
                    "type": "audio",
                    "source": source,
                    "data": base64.b64encode(pcm).decode(),
                }
                writer.write((json.dumps(message) + "\n").encode())
                await writer.drain()
            writer.write((json.dumps({"type": "ping"}) + "\n").encode())
            await writer.drain()
            line = await asyncio.wait_for(reader.readline(), timeout=5)
            return json.loads(line.decode())
        finally:
            writer.close()
            await writer.wait_closed()

    proc, port = _spawn(tmp_path)
    try:
        pong = asyncio.run(scenario(port))
        assert pong["type"] == "pong"
        assert pong["audio_chunks"] == 5
        assert pong["audio_by_source"] == {"mic": 3, "system": 2}
        assert pong["audio_bytes"] > 0
    finally:
        _shutdown(proc)

"""Meetlog AI sidecar.

A local TCP server that the Tauri/Rust layer spawns. It owns the Gemini
provider sessions and streams transcript events back as newline-delimited JSON.

Startup contract: the sidecar prints its listening port to **stdout** as a
single integer line. All diagnostics go to stderr, so stdout stays clean for
the Rust parent to parse.

Wire protocol (newline-delimited JSON, UTF-8):

    client -> server:
        {"type": "start", "config": {...}}
        {"type": "audio", "data": "<base64 16kHz mono int16 PCM>"}
        {"type": "pause"} | {"type": "resume"} | {"type": "stop"}
        {"type": "ping"}

    server -> client:
        {"type": "ready"}
        {"type": "interim", "text", "language", "speaker"}
        {"type": "segment", "segment": {...}}
        {"type": "error", "message"}
        {"type": "system", "message"}
        {"type": "stopped", "folder", "markdown_path", "transcript"}
        {"type": "pong"}
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

from ai.config import GEMINI_LIVE_MODEL, SIDECAR_HOST, api_key
from ai.models.transcript import (
    MeetingMetadata,
    Transcript,
    TranscriptEvent,
    TranscriptSegment,
)
from ai.pipeline import generate_meeting
from ai.stt.gemini import GeminiLiveProvider
from ai.storage.transcript import save_meeting

log = logging.getLogger("meetlog.sidecar")

_BENGALI = range(0x0980, 0x0A00)
_DEVANAGARI = range(0x0900, 0x0980)
_HIRAGANA = range(0x3040, 0x3100)
_KATAKANA = range(0x30A0, 0x3100)
_CJK = range(0x4E00, 0xA000)


def _scripts_present(text: str) -> set[str]:
    """Set of scripts detected in text: bengali, hindi, english, japanese, chinese."""
    scripts: set[str] = set()
    for ch in text:
        o = ord(ch)
        if o in _BENGALI:
            scripts.add("bangla")
        elif o in _DEVANAGARI:
            scripts.add("hindi")
        elif o in _HIRAGANA or o in _KATAKANA:
            scripts.add("japanese")
        elif o in _CJK:
            scripts.add("chinese")
        elif "a" <= ch.lower() <= "z":
            scripts.add("english")
    return scripts


def detect_language(text: str, code: str | None) -> str:
    """Coarse language label.

    Single-script text returns that script's language (bangla, hindi,
    english, japanese, chinese). Japanese kanji (CJK block) alongside kana
    still counts as japanese. Anything genuinely mixed returns "mixed".
    Text with no recognizable script falls back to the provider's language
    code, or "unknown".
    """
    scripts = _scripts_present(text)
    if not scripts:
        return code.lower() if code else "unknown"
    if len(scripts) == 1:
        return next(iter(scripts))
    if scripts <= {"japanese", "chinese"}:
        # Kanji inside Japanese text is still Japanese.
        return "japanese"
    return "mixed"


def normalize_speaker(label: str | None) -> str:
    if not label:
        return "Speaker 1"
    cleaned = str(label).strip()
    if cleaned.isdigit():
        return f"Speaker {cleaned}"
    return cleaned


class SidecarSession:
    """Owns one meeting's provider session and transcript state."""

    def __init__(self, writer: asyncio.StreamWriter) -> None:
        self._writer = writer
        self._send_lock = asyncio.Lock()
        self._provider: GeminiLiveProvider | None = None
        self._forwarder: asyncio.Task | None = None
        self._transcript = Transcript(meeting_id=uuid.uuid4().hex[:12])
        self._metadata: MeetingMetadata | None = None
        self._started_at: datetime | None = None
        self._stopping = False
        self._audio_chunks = 0
        self._audio_bytes = 0
        self._audio_by_source: dict[str, int] = {}

    def stats(self) -> dict[str, Any]:
        return {
            "audio_chunks": self._audio_chunks,
            "audio_bytes": self._audio_bytes,
            "audio_by_source": self._audio_by_source,
        }

    async def send(self, payload: dict[str, Any]) -> None:
        data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        async with self._send_lock:
            self._writer.write(data)
            await self._writer.drain()

    async def start(self, config: dict[str, Any]) -> None:
        key = config.get("api_key") or api_key()
        if not key:
            await self.send(
                {"type": "error", "message": "No Gemini API key configured"}
            )
            return

        now = datetime.now(timezone.utc)
        self._started_at = now
        self._transcript.started_at = now.isoformat()
        self._transcript.provider = "gemini"
        self._transcript.model = config.get("model", GEMINI_LIVE_MODEL)

        self._metadata = MeetingMetadata(
            meeting_id=self._transcript.meeting_id,
            title=config.get("title") or "Meeting",
            date=now.date().isoformat(),
            mode=config.get("mode", "offline"),
            provider="gemini",
            model=self._transcript.model,
        )

        self._provider = GeminiLiveProvider(
            key,
            model=config.get("model") or GEMINI_LIVE_MODEL,
            language_codes=config.get("language_codes") or ["bn-BD", "en-US"],            custom_vocabulary=config.get("custom_vocabulary") or [],
            mode=config.get("transcription_mode", "VERBATIM"),
            diarization=bool(config.get("diarization", False)),
        )
        try:
            await self._provider.connect()
        except Exception as exc:  # noqa: BLE001 - report, don't crash
            await self._provider.disconnect()
            await self.send(
                {"type": "error", "message": f"connect failed: {exc}"}
            )
            return
        await self._provider.start()
        self._forwarder = asyncio.create_task(self._forward_events())
        await self.send({"type": "ready"})

    async def _forward_events(self) -> None:
        assert self._provider is not None
        async for event in self._provider.receive_transcript():
            await self._handle_event(event)

    async def _handle_event(self, event: TranscriptEvent) -> None:
        if event.kind == "interim":
            await self.send(
                {
                    "type": "interim",
                    "text": event.text,
                    "language": detect_language(event.text, event.language),
                    "speaker": normalize_speaker(event.speaker),
                }
            )
        elif event.kind == "segment":
            segment = TranscriptSegment(
                id=self._transcript.next_segment_id(),
                speaker=normalize_speaker(event.speaker),
                start=event.start or 0.0,
                end=event.end or 0.0,
                text=event.text,
                language=detect_language(event.text, event.language),
            )
            self._transcript.add_segment(segment)
            await self.send({"type": "segment", "segment": segment.to_dict()})
        elif event.kind == "error":
            await self.send({"type": "error", "message": event.message})
        elif event.kind == "system":
            await self.send({"type": "system", "message": event.message})

    async def audio(self, b64: str, source: str = "unknown") -> None:
        self._audio_chunks += 1
        self._audio_bytes += len(b64) * 3 // 4  # approximate decoded size
        self._audio_by_source[source] = self._audio_by_source.get(source, 0) + 1
        if self._provider is None:
            return
        try:
            pcm = base64.b64decode(b64)
        except (ValueError, TypeError) as exc:
            await self.send({"type": "error", "message": f"bad audio chunk: {exc}"})
            return
        await self._provider.send_audio(pcm)

    async def pause(self) -> None:
        if self._provider is not None:
            await self._provider.pause()

    async def resume(self) -> None:
        if self._provider is not None:
            await self._provider.resume()

    async def stop(self, config: dict[str, Any]) -> None:
        if self._stopping:
            return
        self._stopping = True

        if self._provider is not None:
            await self._provider.stop()  # flush final transcripts
            await asyncio.sleep(1.5)
            await self._provider.disconnect()
        if self._forwarder is not None:
            self._forwarder.cancel()
            try:
                await self._forwarder
            except asyncio.CancelledError:
                pass
            self._forwarder = None

        if self._metadata is not None:
            self._metadata.ended_at = None
            if self._started_at is not None:
                self._metadata.duration_seconds = (
                    datetime.now(timezone.utc) - self._started_at
                ).total_seconds()

        folder = None
        markdown_path = None
        try:
            if self._metadata is not None:
                save_meeting(self._metadata, self._transcript)
            key = config.get("api_key") or api_key()
            if (
                self._metadata is not None
                and key
                and config.get("generate_markdown", True)
                and self._transcript.segments
            ):
                _, folder, _ = await generate_meeting(
                    self._transcript, self._metadata, api_key=key
                )
                markdown_path = str(folder / "meeting.md")
            elif self._metadata is not None:
                folder = save_meeting(self._metadata, self._transcript)
        except Exception as exc:  # noqa: BLE001 - report, never crash the sidecar
            log.exception("meeting generation failed")
            await self.send(
                {"type": "error", "message": f"generation failed: {exc}"}
            )

        await self.send(
            {
                "type": "stopped",
                "folder": str(folder) if folder else None,
                "markdown_path": markdown_path,
                "transcript": self._transcript.to_dict(),
            }
        )


async def handle_client(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    peer = writer.get_extra_info("peername")
    log.info("client connected: %s", peer)
    session = SidecarSession(writer)
    try:
        while True:
            line = await reader.readline()
            if not line:
                break
            try:
                message = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError as exc:
                await session.send({"type": "error", "message": f"bad json: {exc}"})
                continue

            msg_type = message.get("type")
            if msg_type == "start":
                await session.start(message.get("config", {}))
            elif msg_type == "audio":
                await session.audio(message.get("data", ""), message.get("source", "unknown"))
            elif msg_type == "pause":
                await session.pause()
            elif msg_type == "resume":
                await session.resume()
            elif msg_type == "stop":
                await session.stop(message.get("config", {}))
            elif msg_type == "ping":
                await session.send({"type": "pong", **session.stats()})
            else:
                await session.send(
                    {"type": "error", "message": f"unknown message type: {msg_type}"}
                )
    except (ConnectionResetError, asyncio.IncompleteReadError):
        log.info("client disconnected: %s", peer)
    finally:
        try:
            if session._provider is not None:
                await session._provider.disconnect()
        except Exception:  # noqa: BLE001
            pass
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass


async def serve(host: str, port: int) -> tuple[asyncio.AbstractServer, int]:
    server = await asyncio.start_server(handle_client, host, port)
    bound_port = server.sockets[0].getsockname()[1]
    return server, bound_port


def main() -> None:
    parser = argparse.ArgumentParser(description="Meetlog AI sidecar")
    parser.add_argument("--host", default=SIDECAR_HOST)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    async def runner() -> None:
        server, bound_port = await serve(args.host, args.port)
        # The port line is the sidecar's startup contract with the Rust parent.
        print(bound_port, flush=True)
        log.info("sidecar listening on %s:%s", args.host, bound_port)
        async with server:
            await server.serve_forever()

    try:
        asyncio.run(runner())
    except KeyboardInterrupt:
        log.info("sidecar shutting down")


if __name__ == "__main__":
    main()

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
        {"type": "rename_speaker", "from": "Speaker 1", "to": "Tauhid"}
        {"type": "ping"}

    server -> client:
        {"type": "ready"}
        {"type": "interim", "text", "language", "speaker"}
        {"type": "segment", "segment": {...}}
        {"type": "speakers", "speakers": [...]}
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
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any

import numpy as np

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


def resolve_speaker(label: str | None, names: dict[str, str] | None = None) -> str:
    """Map a provider speaker label to its display name.

    `names` maps canonical ids ("Speaker 1") to user-chosen names. Raw words
    and timestamps are never touched; only the label is resolved.
    """
    canonical = normalize_speaker(label)
    if names:
        return names.get(canonical, canonical)
    return canonical


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
        self._speaker_names: dict[str, str] = {}
        # Trailing per-source audio activity as (monotonic_time, source, rms),
        # used to attribute segments the model leaves unlabeled. Bounded to
        # roughly the last 3 minutes at 100 ms chunks from two sources.
        self._activity: deque[tuple[float, str, float]] = deque(maxlen=3600)

    def stats(self) -> dict[str, Any]:
        return {
            "audio_chunks": self._audio_chunks,
            "audio_bytes": self._audio_bytes,
            "audio_by_source": self._audio_by_source,
        }

    def _display_speaker(self, label: str | None) -> str:
        return resolve_speaker(label, self._speaker_names)

    def _note_activity(self, source: str, pcm: bytes) -> None:
        """Record audio energy per source for fallback speaker attribution."""
        if len(pcm) < 2:
            return
        samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
        if samples.size == 0:
            return
        rms = float(np.sqrt(np.mean(samples * samples)))
        self._activity.append((time.monotonic(), source, rms))

    def _fallback_speaker(self) -> str | None:
        """Attribute by dominant recent source when the model gives no label.

        Online meetings capture two sources: the microphone (the local user)
        and system audio (remote participants). When a finalized segment has
        no model speaker label, the source that dominated the trailing audio
        window decides: "You" for the mic, "Guest" for system audio. Returns
        None when attribution is inconclusive so the caller keeps the default.
        Only applies to online meetings; offline has a single source.
        """
        if self._metadata is None or self._metadata.mode != "online":
            return None
        cutoff = time.monotonic() - 5.0
        mic = sys_total = 0.0
        for ts, source, rms in self._activity:
            if ts < cutoff:
                continue
            if source == "mic":
                mic += rms
            elif source == "system":
                sys_total += rms
        floor = 0.01
        if mic < floor and sys_total < floor:
            return None
        if mic >= 1.5 * max(sys_total, 1e-6):
            return "You"
        if sys_total >= 1.5 * max(mic, 1e-6):
            return "Guest"
        return None

    def _speaker_for(self, label: str | None) -> str:
        """Resolve a speaker: model label wins, else source-activity fallback.

        Both paths go through the rename mapping so a renamed fallback label
        ("You" -> "Tauhid") stays renamed on later segments too.
        """
        cleaned = (label or "").strip() or None
        if cleaned:
            return self._display_speaker(cleaned)
        fallback = self._fallback_speaker()
        if fallback:
            return self._display_speaker(fallback)
        return "Speaker 1"

    def speakers(self) -> list[str]:
        """Display names in order of first appearance."""
        seen: list[str] = []
        for seg in self._transcript.segments:
            if seg.speaker not in seen:
                seen.append(seg.speaker)
        return seen

    def _resolve_canonical(self, source: str) -> str | None:
        """Resolve a rename source to a canonical speaker id.

        Accepts a canonical id ("Speaker 1"), a current display name, and
        either casing. Returns None for speakers never seen.
        """
        want = source.strip().lower()
        for key in self._speaker_names:
            if key.lower() == want:
                return key
        for key, val in self._speaker_names.items():
            if val.lower() == want:
                return key
        stored = {seg.speaker for seg in self._transcript.segments}
        for name in stored:
            if name.lower() == want:
                return normalize_speaker(name)
        return None

    async def rename_speaker(self, from_label: str | None, to_name: str | None) -> bool:
        """Rename a speaker everywhere: past segments, future segments, output.

        Returns True when applied. Past segment words and timestamps are
        untouched; only labels change. Renaming two speakers to the same name
        merges them in display, which is reported back in the speakers event.
        """
        display = (to_name or "").strip()
        if not display:
            await self.send({"type": "error", "message": "speaker name must not be empty"})
            return False
        source = (from_label or "").strip()
        if not source:
            await self.send({"type": "error", "message": "speaker to rename must be specified"})
            return False
        canonical = self._resolve_canonical(source)
        if canonical is None:
            await self.send({"type": "error", "message": f"unknown speaker: {source}"})
            return False
        previous = self._speaker_names.get(canonical, canonical)
        self._speaker_names[canonical] = display
        for seg in self._transcript.segments:
            if seg.speaker == previous:
                seg.speaker = display
        await self.send({"type": "speakers", "speakers": self.speakers()})
        return True

    async def send(self, payload: dict[str, Any]) -> None:
        data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        async with self._send_lock:
            self._writer.write(data)
            await self._writer.drain()

    async def _reset_for_new_meeting(self) -> None:
        """Clear all previous-meeting state so back-to-back meetings in one
        app session never share transcript, speakers, provider, or flags."""
        if self._forwarder is not None:
            self._forwarder.cancel()
            try:
                await self._forwarder
            except asyncio.CancelledError:
                pass
            self._forwarder = None
        if self._provider is not None:
            await self._provider.disconnect()
            self._provider = None
        self._transcript = Transcript(meeting_id=uuid.uuid4().hex[:12])
        self._speaker_names = {}
        self._metadata = None
        self._started_at = None
        self._stopping = False
        self._audio_chunks = 0
        self._audio_bytes = 0
        self._audio_by_source = {}
        self._activity.clear()

    async def start(self, config: dict[str, Any]) -> None:
        key = config.get("api_key") or api_key()
        if not key:
            await self.send(
                {"type": "error", "message": "No Gemini API key configured"}
            )
            return

        await self._reset_for_new_meeting()

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
            diarization=bool(config.get("diarization", True)),
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
                    "speaker": self._speaker_for(event.speaker),
                }
            )
        elif event.kind == "segment":
            segment = TranscriptSegment(
                id=self._transcript.next_segment_id(),
                speaker=self._speaker_for(event.speaker),
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
        try:
            pcm = base64.b64decode(b64)
        except (ValueError, TypeError) as exc:
            await self.send({"type": "error", "message": f"bad audio chunk: {exc}"})
            return
        self._note_activity(source, pcm)
        if self._provider is None:
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
            now = datetime.now(timezone.utc)
            self._metadata.ended_at = now.isoformat()
            if self._started_at is not None:
                self._metadata.duration_seconds = (
                    now - self._started_at
                ).total_seconds()
            self._metadata.participants = self.speakers()

        folder = None
        markdown_path = None
        try:
            if self._metadata is not None:
                folder = save_meeting(self._metadata, self._transcript)
            key = config.get("api_key") or api_key()
            if (
                self._metadata is not None
                and folder is not None
                and key
                and config.get("generate_markdown", True)
                and self._transcript.segments
            ):
                try:
                    _, folder, _ = await generate_meeting(
                        self._transcript, self._metadata, api_key=key
                    )
                    markdown_path = str(folder / "meeting.md")
                except Exception as exc:  # noqa: BLE001 - keep the raw-save folder
                    log.exception("meeting intelligence failed")
                    await self.send(
                        {"type": "error", "message": f"generation failed: {exc}"}
                    )
        except Exception as exc:  # noqa: BLE001 - report, never crash the sidecar
            log.exception("meeting save failed")
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
            elif msg_type == "rename_speaker":
                await session.rename_speaker(message.get("from"), message.get("to"))
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

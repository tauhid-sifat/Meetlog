r"""Validate long-session continuity and session rotation.

Streams a looping clip in real time while forcing a short rotation interval, so
the >10-minute rotation path can be exercised quickly. Verifies that the
provider reconnects across the boundary and keeps producing transcripts.

    $env:GEMINI_API_KEY = "..."
    .\.venv\Scripts\python.exe -m scripts.validate_rotation --seconds 45 --rotate 12
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

from ai.audio_utils import chunk_pcm, read_wav_mono_16k
from ai.config import CHUNK_BYTES, CHUNK_MS, api_key
from ai.models.transcript import TranscriptEvent
from ai.stt.gemini import GeminiLiveProvider


def _looped_pcm(path: Path, seconds: float) -> bytes:
    pcm = read_wav_mono_16k(path)
    target = int(seconds * 16000) * 2
    if not pcm:
        raise SystemExit(f"no audio in {path}")
    repeats = (target // len(pcm)) + 1
    return (pcm * repeats)[:target]


async def run(args: argparse.Namespace) -> int:
    key = args.api_key or api_key()
    if not key:
        print("error: set GEMINI_API_KEY", file=sys.stderr)
        return 2

    clip = Path(args.clip)
    if not clip.exists():
        print(f"error: clip not found: {clip}", file=sys.stderr)
        return 2

    pcm = _looped_pcm(clip, args.seconds)
    provider = GeminiLiveProvider(
        key,
        model=args.model,
        language_codes=args.language,
        session_max_seconds=args.rotate,
    )

    connects = 0
    segments: list[tuple[float, str]] = []
    errors: list[str] = []

    async def receiver() -> None:
        nonlocal connects
        async for event in provider.receive_transcript():
            if event.kind == "system" and event.message == "session_connected":
                connects += 1
                print(f"[t={time.monotonic() - t0:5.1f}s] session connected (#{connects})")
            elif event.kind == "segment" and event.text:
                segments.append((time.monotonic() - t0, event.text))
                print(f"[t={time.monotonic() - t0:5.1f}s] segment: {event.text}")
            elif event.kind == "error":
                errors.append(event.message)
                print(f"[t={time.monotonic() - t0:5.1f}s] ERROR: {event.message}")

    await provider.connect()
    await provider.start()
    t0 = time.monotonic()
    recv = asyncio.create_task(receiver())

    for chunk in chunk_pcm(pcm, CHUNK_BYTES):
        await provider.send_audio(chunk)
        await asyncio.sleep(CHUNK_MS / 1000)
    await provider.stop()
    await asyncio.sleep(3.0)
    await provider.disconnect()
    recv.cancel()
    try:
        await recv
    except asyncio.CancelledError:
        pass

    print("\n--- summary ---")
    print(f"requested duration : {args.seconds:.0f}s")
    print(f"rotation interval  : {args.rotate:.0f}s")
    print(f"session connects   : {connects}")
    print(f"segments received  : {len(segments)}")
    print(f"errors             : {errors}")

    expected_rotations = max(1, int(args.seconds // args.rotate))
    ok = connects >= 2 and len(segments) > 0 and not errors
    print(f"rotations expected : ~{expected_rotations}, observed connects {connects}")
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Validate session rotation")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--clip", default="tests/data/_tts/english.wav")
    parser.add_argument("--seconds", type=float, default=45.0)
    parser.add_argument("--rotate", type=float, default=12.0)
    parser.add_argument("--model", default="gemini-3.5-transcribe-live")
    parser.add_argument("--language", action="append", default=[])
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()

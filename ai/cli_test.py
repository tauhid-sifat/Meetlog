"""Microphone transcription harness (Phase 1).

Captures the microphone with sounddevice, streams 16 kHz mono PCM to a
Gemini Live provider, and prints the live transcript. Also writes the raw
transcript to ``transcript.json``.

Usage:
    python -m ai.cli_test --seconds 30
    python -m ai.cli_test --language en-US --language bn-BD
    python -m ai.cli_test --vocab "Caboodle,FortiMapp,Constance,Efti"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import sounddevice as sd

from ai.config import CHUNK_BYTES, GEMINI_LIVE_MODEL, SAMPLE_RATE, api_key
from ai.main import detect_language, normalize_speaker
from ai.models.transcript import Transcript, TranscriptSegment
from ai.stt.gemini import GeminiLiveProvider


async def run(args: argparse.Namespace) -> int:
    key = args.api_key or api_key()
    if not key:
        print(
            "error: no Gemini API key. Set GEMINI_API_KEY or pass --api-key.",
            file=sys.stderr,
        )
        return 2

    provider = GeminiLiveProvider(
        key,
        model=args.model,
        language_codes=args.language,
        custom_vocabulary=args.vocab,
        mode=args.mode,
        diarization=args.diarization,
    )
    await provider.connect()
    await provider.start()

    transcript = Transcript(
        meeting_id=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        started_at=datetime.now(timezone.utc).isoformat(),
        provider="gemini",
        model=args.model,
    )

    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def on_audio(indata, _frames, _time, status) -> None:
        if status:
            print(f"[audio status] {status}", file=sys.stderr)
        loop.call_soon_threadsafe(queue.put_nowait, bytes(indata))

    async def sender() -> None:
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            await provider.send_audio(chunk)

    async def receiver() -> None:
        async for event in provider.receive_transcript():
            if event.kind == "interim" and event.text:
                print(f"\r... {event.text}", end="", flush=True)
            elif event.kind == "segment" and event.text:
                language = detect_language(event.text, event.language)
                speaker = normalize_speaker(event.speaker)
                segment = TranscriptSegment(
                    id=transcript.next_segment_id(),
                    speaker=speaker,
                    start=event.start or 0.0,
                    end=event.end or 0.0,
                    text=event.text,
                    language=language,
                )
                transcript.add_segment(segment)
                print(f"\n[{speaker}] ({language}) {event.text}")
            elif event.kind == "error":
                print(f"\n[error] {event.message}", file=sys.stderr)
            elif event.kind == "system" and args.verbose:
                print(f"\n[system] {event.message}", file=sys.stderr)

    stream = sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=CHUNK_BYTES // 2,
        device=args.device,
        callback=on_audio,
    )
    stream.start()

    sender_task = asyncio.create_task(sender())
    receiver_task = asyncio.create_task(receiver())

    print(f"Recording for {args.seconds}s at {SAMPLE_RATE} Hz... (Ctrl+C to stop)")
    try:
        await asyncio.sleep(args.seconds)
    except asyncio.CancelledError:
        pass
    finally:
        stream.stop()
        stream.close()
        await queue.put(None)
        await sender_task
        await provider.stop()  # flush final transcripts
        await asyncio.sleep(2.0)
        await provider.disconnect()
        receiver_task.cancel()
        try:
            await receiver_task
        except asyncio.CancelledError:
            pass

    transcript.ended_at = datetime.now(timezone.utc).isoformat()
    out = Path(args.out)
    out.write_text(
        json.dumps(transcript.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nWrote {len(transcript.segments)} segments to {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Meetlog mic transcription test")
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--model", default=GEMINI_LIVE_MODEL)
    parser.add_argument("--language", action="append", default=[], help="BCP-47 code")
    parser.add_argument("--vocab", default="", help="comma-separated custom terms")
    parser.add_argument("--mode", default="VERBATIM", choices=["VERBATIM", "SMART"])
    parser.add_argument("--diarization", action="store_true")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--device", type=int, default=None, help="input device index")
    parser.add_argument("--out", default="transcript.json")
    parser.add_argument("--list-devices", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    if args.list_devices:
        print(sd.query_devices())
        return
    args.vocab = [t.strip() for t in args.vocab.split(",") if t.strip()]
    try:
        raise SystemExit(asyncio.run(run(args)))
    except KeyboardInterrupt:
        raise SystemExit(130)


if __name__ == "__main__":
    main()

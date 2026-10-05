"""STT benchmark harness (Phase 0).

Streams a WAV file through a Gemini Live provider and scores the transcript
against a ground-truth reference using WER and CER.

Usage:
    python -m ai.benchmark.run_benchmark --audio tests/data/meeting1.wav \\
        --reference tests/data/meeting1.txt --language en-US

The reference is read from a file when the path exists, otherwise treated as
literal text. Use --fast to send audio as quickly as possible instead of
pacing it at real time.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import jiwer

from ai.audio_utils import chunk_pcm, read_wav_mono_16k
from ai.config import (
    CHUNK_BYTES,
    CHUNK_MS,
    GEMINI_LIVE_MODEL,
    SAMPLE_RATE,
    api_key,
)
from ai.main import detect_language
from ai.stt.gemini import GeminiLiveProvider


def _read_reference(reference: str) -> str:
    path = Path(reference)
    if path.exists() and path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return reference.strip()


def _normalize(text: str) -> str:
    return " ".join(text.split()).strip()


async def benchmark_file(
    audio_path: Path | str,
    reference: str,
    *,
    key: str,
    model: str = GEMINI_LIVE_MODEL,
    language_codes: list[str] | None = None,
    vocabulary: list[str] | None = None,
    mode: str = "VERBATIM",
    diarization: bool = False,
    realtime: bool = True,
) -> dict:
    """Transcribe ``audio_path`` and score it against ``reference``."""
    pcm = read_wav_mono_16k(audio_path)
    audio_seconds = len(pcm) / (SAMPLE_RATE * 2)

    provider = GeminiLiveProvider(
        key,
        model=model,
        language_codes=language_codes or [],
        custom_vocabulary=vocabulary or [],
        mode=mode,
        diarization=diarization,
    )
    await provider.connect()
    await provider.start()

    segments: list[str] = []
    languages: list[str] = []
    errors: list[str] = []

    async def receiver() -> None:
        async for event in provider.receive_transcript():
            if event.kind == "segment" and event.text:
                segments.append(event.text)
                languages.append(detect_language(event.text, event.language))
            elif event.kind == "error":
                errors.append(event.message)

    recv_task = asyncio.create_task(receiver())

    started = time.monotonic()
    for chunk in chunk_pcm(pcm, CHUNK_BYTES):
        await provider.send_audio(chunk)
        if realtime:
            await asyncio.sleep(CHUNK_MS / 1000)
    await asyncio.sleep(2.0)  # allow trailing finals to arrive
    await provider.stop()
    await asyncio.sleep(1.0)
    await provider.disconnect()
    recv_task.cancel()
    try:
        await recv_task
    except asyncio.CancelledError:
        pass

    elapsed = time.monotonic() - started
    hypothesis = _normalize(" ".join(segments))
    reference_text = _normalize(_read_reference(reference))

    if reference_text and hypothesis:
        wer = jiwer.wer(reference_text, hypothesis)
        cer = jiwer.cer(reference_text, hypothesis)
    else:
        wer = cer = 1.0

    return {
        "audio": str(audio_path),
        "model": model,
        "audio_seconds": round(audio_seconds, 2),
        "wall_seconds": round(elapsed, 2),
        "real_time_factor": round(elapsed / audio_seconds, 3) if audio_seconds else None,
        "segments": len(segments),
        "languages": sorted(set(languages)),
        "wer": round(wer, 4),
        "cer": round(cer, 4),
        "errors": errors,
        "hypothesis": hypothesis,
        "reference": reference_text,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Meetlog STT benchmark")
    parser.add_argument("--audio", required=True, help="path to a 16-bit WAV file")
    parser.add_argument("--reference", required=True, help="path or literal text")
    parser.add_argument("--model", default=GEMINI_LIVE_MODEL)
    parser.add_argument("--language", action="append", default=[])
    parser.add_argument("--vocab", default="")
    parser.add_argument("--mode", default="VERBATIM", choices=["VERBATIM", "SMART"])
    parser.add_argument("--diarization", action="store_true")
    parser.add_argument("--fast", action="store_true", help="do not pace at real time")
    parser.add_argument("--json", dest="json_out", default="")
    args = parser.parse_args()

    key = api_key()
    if not key:
        print("error: set GEMINI_API_KEY", file=sys.stderr)
        raise SystemExit(2)

    vocabulary = [t.strip() for t in args.vocab.split(",") if t.strip()]
    result = asyncio.run(
        benchmark_file(
            args.audio,
            args.reference,
            key=key,
            model=args.model,
            language_codes=args.language,
            vocabulary=vocabulary,
            mode=args.mode,
            diarization=args.diarization,
            realtime=not args.fast,
        )
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )


if __name__ == "__main__":
    main()

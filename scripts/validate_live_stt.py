r"""Validate the live Gemini STT path without a microphone.

Synthesizes speech with Gemini TTS, writes it to a WAV, then streams it through
the real ``gemini-3.5-transcribe-live`` provider and scores the transcript.

    $env:GEMINI_API_KEY = "..."
    .\.venv\Scripts\python.exe -m scripts.validate_live_stt
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from google import genai

from ai.benchmark.run_benchmark import benchmark_file
from ai.config import api_key
from scripts.tts import synthesize

LIVE_MODEL = "gemini-3.5-transcribe-live"

CASES = [
    ("english", "We should finalize this feature before Thursday."),
    ("bangla", "আমাদের এটা বৃহস্পতিবারের মধ্যে ফাইনাল করতে হবে।"),
    ("mixed", "আমাদের Thursday-এর মধ্যে এটা finalize করতে হবে।"),
]


async def run(args: argparse.Namespace) -> int:
    key = args.api_key or api_key()
    if not key:
        print("error: set GEMINI_API_KEY", file=sys.stderr)
        return 2

    client = genai.Client(api_key=key)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    failures = 0
    for label, text in CASES:
        wav_path = out_dir / f"{label}.wav"
        synthesize(client, text, wav_path, args.voice)
        print(f"\n=== {label} ===")
        print(f"reference: {text}")
        result = await benchmark_file(
            wav_path,
            text,
            key=key,
            model=LIVE_MODEL,
            language_codes=args.language,
            realtime=False,
        )
        print(f"hypothesis: {result['hypothesis']}")
        print(f"WER={result['wer']}  CER={result['cer']}  errors={result['errors']}")
        if result["errors"] or result["wer"] > args.max_wer:
            failures += 1

    print(f"\n{len(CASES) - failures}/{len(CASES)} cases within WER <= {args.max_wer}")
    return 1 if failures else 0


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Validate live Gemini STT")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--voice", default="Kore")
    parser.add_argument("--language", action="append", default=[])
    parser.add_argument("--max-wer", type=float, default=0.5)
    parser.add_argument("--out-dir", default="tests/data/_tts")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()

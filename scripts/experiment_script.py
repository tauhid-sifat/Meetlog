r"""Ablation for the mixed-language script-normalization issue.

Runs the same cached clips through several provider configurations to see which
(if any) preserves Latin script for English words in Bengali/Banglish speech.
Uses cached WAVs, so no TTS quota is consumed.

    $env:GEMINI_API_KEY = "..."
    .\.venv\Scripts\python.exe -m scripts.experiment_script
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from ai.benchmark.run_benchmark import benchmark_file
from ai.config import api_key

LIVE_MODEL = "gemini-3.5-transcribe-live"

INSTRUCTION = (
    "Transcribe verbatim in the script that was actually spoken. Write English "
    "words and English technical terms in Latin script. Write Bengali words in "
    "Bengali script. Never transliterate English words into Bengali script."
)

CLIPS: list[tuple[str, Path, str]] = [
    ("mixed", Path("tests/data/_tts/mixed.wav"), "আমাদের Thursday-এর মধ্যে এটা finalize করতে হবে।"),
    ("banglish", Path("tests/data/_tts_terms/banglish.wav"), "Eta basically existing workflow-er sathei integrate hobe."),
]

VOCAB = ["Thursday", "finalize", "basically", "existing", "workflow", "integrate"]

# Note: the provider defaults to language_codes=["bn-BD", "en-US"], so the
# baseline below is already constrained. There is no unconstrained variant on
# purpose: unconstrained output is out of scope for this product.
VARIANTS: list[tuple[str, dict]] = [
    ("baseline", {}),
    ("lang-bn-en-hint", {"language_codes": ["bn-BD", "en-US"], "language_hints": ["bn-BD", "en-US"]}),
    ("sys-instr", {"system_instruction": INSTRUCTION}),
    ("vocab", {"vocabulary": VOCAB}),
    ("lang+vocab", {"language_codes": ["bn-BD", "en-US"], "vocabulary": VOCAB}),
]


def _script_mix(text: str) -> str:
    bengali = sum(1 for ch in text if 0x0980 <= ord(ch) < 0x0A00)
    latin = sum(1 for ch in text if "a" <= ch.lower() <= "z")
    return f"latin={latin} bengali={bengali}"


async def run(args: argparse.Namespace) -> int:
    key = args.api_key or api_key()
    if not key:
        print("error: set GEMINI_API_KEY", file=sys.stderr)
        return 2

    for label, wav, reference in CLIPS:
        if not wav.exists():
            print(f"skip {label}: {wav} not found", file=sys.stderr)
            continue
        print(f"\n{'=' * 70}\nCLIP {label}\n  reference: {reference}")
        variants = [
            (n, k) for n, k in VARIANTS if not args.only or n in args.only
        ]
        for variant, kwargs in variants:
            try:
                result = await benchmark_file(
                    wav,
                    reference,
                    key=key,
                    model=LIVE_MODEL,
                    realtime=False,
                    **kwargs,
                )
            except Exception as exc:  # noqa: BLE001 - report and continue
                print(f"\n  [{variant}] FAILED: {exc}")
                continue
            print(f"\n  [{variant}] WER={result['wer']:.3f} ({_script_mix(result['hypothesis'])})")
            print(f"    {result['hypothesis']}")
    return 0


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Script-normalization ablation")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--only", default="", help="comma-separated variant names")
    args = parser.parse_args()
    args.only = {v.strip() for v in args.only.split(",") if v.strip()}
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()

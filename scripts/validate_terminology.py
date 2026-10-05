r"""Mixed-language and terminology benchmark (script preservation).

TTS-synthesizes sentences that mix English and Bangla and checks whether the
English tokens survive in Latin script. Directly targets the finding that
``Thursday`` came back as ``থার্সডে``.

    $env:GEMINI_API_KEY = "..."
    .\.venv\Scripts\python.exe -m scripts.validate_terminology
    .\.venv\Scripts\python.exe -m scripts.validate_terminology --vocab "Thursday,FortiMapp,Caboodle,RBAC,IAM,Jira,Figma"
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

CASES: list[tuple[str, str, list[str]]] = [
    ("english_in_bangla", "Thursday te client review ache.", ["Thursday", "client", "review"]),
    ("bangla_in_english", "We should finalize it, kintu deadline ta tight.", ["finalize", "deadline"]),
    ("banglish", "Eta basically existing workflow-er sathei integrate hobe.", ["basically", "existing", "workflow", "integrate"]),
    ("names_products", "Constance will update the Figma file and open a Jira ticket.", ["Constance", "Figma", "Jira"]),
    ("dates_numbers", "The deadline is October 8, 2026 at 3 PM.", ["October"]),
    ("tech_in_bangla", "আমাদের RBAC আর IAM নিয়ে কাজ করতে হবে।", ["RBAC", "IAM"]),
    ("internal_terms", "Please check the FortiMapp endpoint and the Caboodle integration.", ["FortiMapp", "Caboodle"]),
    ("count_in_bangla", "Meeting e 25 jon attend korbe.", ["25"]),
]


def _preserved(hypothesis: str, tokens: list[str]) -> tuple[int, list[str]]:
    lowered = hypothesis.lower()
    survivors = [t for t in tokens if t.lower() in lowered]
    return len(survivors), survivors


async def run(args: argparse.Namespace) -> int:
    key = args.api_key or api_key()
    if not key:
        print("error: set GEMINI_API_KEY", file=sys.stderr)
        return 2

    client = genai.Client(api_key=key)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    vocab = [t.strip() for t in args.vocab.split(",") if t.strip()]
    total_tokens = 0
    total_survived = 0
    wer_values: list[float] = []

    for label, text, tokens in CASES:
        wav = out_dir / f"{label}.wav"
        synthesize(client, text, wav, args.voice)
        result = await benchmark_file(
            wav,
            text,
            key=key,
            model=LIVE_MODEL,
            vocabulary=vocab,
            realtime=False,
        )
        survived, survivors = _preserved(result["hypothesis"], tokens)
        total_tokens += len(tokens)
        total_survived += survived
        wer_values.append(result["wer"])
        print(f"\n=== {label} ===")
        print(f"  spoken    : {text}")
        print(f"  transcript: {result['hypothesis']}")
        print(f"  WER {result['wer']:.3f}  latin-tokens {survived}/{len(tokens)} -> {survivors}")

    avg_wer = sum(wer_values) / len(wer_values) if wer_values else 0.0
    print("\n--- summary ---")
    if vocab:
        print(f"custom vocabulary: {vocab}")
    print(f"avg WER          : {avg_wer:.3f}")
    print(f"latin preserved  : {total_survived}/{total_tokens} "
          f"({100 * total_survived / total_tokens:.0f}%)")
    return 0


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Mixed-language terminology benchmark")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--vocab", default="")
    parser.add_argument("--voice", default="Kore")
    parser.add_argument("--out-dir", default="tests/data/_tts_terms")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()

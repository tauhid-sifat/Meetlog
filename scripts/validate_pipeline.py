r"""Validate the transcript -> intelligence -> Markdown pipeline live.

Runs meeting intelligence on a sample transcript (or a transcript.json file)
and prints the generated Markdown.

    $env:GEMINI_API_KEY = "..."
    .\.venv\Scripts\python.exe -m scripts.validate_pipeline
    .\.venv\Scripts\python.exe -m scripts.validate_pipeline --transcript transcript.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

from ai.config import api_key
from ai.models.transcript import (
    MeetingMetadata,
    Transcript,
    TranscriptSegment,
)
from ai.pipeline import generate_meeting

SAMPLE_SEGMENTS = [
    (0.0, 4.0, "Let's decide on the release date. I think we should ship v1 next Thursday."),
    (4.0, 8.0, "Agreed. I'll update the documentation by Wednesday."),
    (8.0, 12.0, "Great. Also, should we include the UI work in this sprint?"),
    (12.0, 15.0, "Let's leave that as an open question for now."),
]


def _sample_transcript() -> Transcript:
    return Transcript(
        meeting_id="sample",
        segments=[
            TranscriptSegment(
                id=f"segment_{i + 1:03d}",
                speaker=f"Speaker {1 + (i % 2)}",
                start=start,
                end=end,
                text=text,
                language="english",
            )
            for i, (start, end, text) in enumerate(SAMPLE_SEGMENTS)
        ],
    )


def _load_transcript(path: Path) -> Transcript:
    return Transcript.from_dict(json.loads(path.read_text(encoding="utf-8")))


async def run(args: argparse.Namespace) -> int:
    key = args.api_key or api_key()
    if not key:
        print("error: set GEMINI_API_KEY", file=sys.stderr)
        return 2

    transcript = (
        _load_transcript(Path(args.transcript)) if args.transcript else _sample_transcript()
    )
    metadata = MeetingMetadata(
        meeting_id=transcript.meeting_id,
        title="Release Planning",
        date=date.today().isoformat(),
        duration_seconds=15.0,
        mode="online",
        participants=sorted({s.speaker for s in transcript.segments}),
    )

    markdown, folder, structured = await generate_meeting(
        transcript, metadata, api_key=key
    )
    print("=" * 60)
    print(markdown)
    print("=" * 60)
    print(f"folder: {folder}")
    print(f"decisions={len(structured.decisions)} "
          f"action_items={len(structured.action_items)} "
          f"open_questions={len(structured.open_questions)}")
    return 0


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Validate the meeting pipeline")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--transcript", default="")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()

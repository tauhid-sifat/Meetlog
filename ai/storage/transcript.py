"""Local, file-based meeting storage.

Every meeting produces a folder::

    Meetings/
    └── 2026-10-05 - Feature Discussion/
        ├── meeting.md
        ├── transcript.json
        └── metadata.json

The raw transcript is written independently of the Markdown so a failed or
poor intelligence pass never destroys the source record.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ai.config import DEFAULT_MEETINGS_DIR
from ai.models.transcript import MeetingMetadata, StructuredMeetingData, Transcript

_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_name(name: str, *, fallback: str = "Meeting") -> str:
    """Make a string safe to use as a Windows folder name."""
    cleaned = _INVALID_CHARS.sub("-", name or "").strip().strip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or fallback


def meeting_dir(
    metadata: MeetingMetadata, meetings_dir: Path | str = DEFAULT_MEETINGS_DIR
) -> Path:
    """Return the target folder for a meeting without creating it."""
    base = Path(meetings_dir)
    date_part = metadata.date or "undated"
    title_part = sanitize_name(metadata.title or metadata.meeting_id)
    return base / f"{date_part} - {title_part}"


def save_meeting(
    metadata: MeetingMetadata,
    transcript: Transcript,
    *,
    markdown: str | None = None,
    structured: StructuredMeetingData | None = None,
    meetings_dir: Path | str = DEFAULT_MEETINGS_DIR,
) -> Path:
    """Persist a meeting folder and return its path.

    ``transcript.json`` and ``metadata.json`` are always written. ``meeting.md``
    is written only when ``markdown`` is provided.
    """
    folder = meeting_dir(metadata, meetings_dir)
    folder.mkdir(parents=True, exist_ok=True)

    (folder / "transcript.json").write_text(
        json.dumps(transcript.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    metadata_payload = metadata.to_dict()
    if structured is not None:
        metadata_payload["structured"] = structured.to_dict()
    (folder / "metadata.json").write_text(
        json.dumps(metadata_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if markdown is not None:
        (folder / "meeting.md").write_text(markdown, encoding="utf-8")

    return folder


def list_meetings(meetings_dir: Path | str = DEFAULT_MEETINGS_DIR) -> list[Path]:
    """Return meeting folders, newest first."""
    base = Path(meetings_dir)
    if not base.exists():
        return []
    folders = [p for p in base.iterdir() if p.is_dir()]
    return sorted(folders, key=lambda p: p.name, reverse=True)

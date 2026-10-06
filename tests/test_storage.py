"""Tests for local meeting storage."""

from __future__ import annotations

import json

from ai.models.transcript import (
    MeetingMetadata,
    StructuredMeetingData,
    Transcript,
    TranscriptSegment,
)
from ai.render.markdown import render_markdown
from ai.storage.transcript import (
    list_meetings,
    meeting_dir,
    sanitize_name,
    save_meeting,
)


def _metadata() -> MeetingMetadata:
    return MeetingMetadata(
        meeting_id="m1",
        title="Feature Discussion",
        date="2026-10-05",
        duration_seconds=120,
        mode="online",
    )


def _transcript() -> Transcript:
    return Transcript(
        meeting_id="m1",
        segments=[
            TranscriptSegment("segment_001", "Speaker 1", 0.0, 2.0, "Hello."),
        ],
    )


def test_sanitize_name_strips_invalid_chars():
    assert sanitize_name('a/b:c*d?') == "a-b-c-d-"
    assert sanitize_name("   ") == "Meeting"


def test_meeting_dir_uses_date_and_title(tmp_path):
    folder = meeting_dir(_metadata(), tmp_path)
    assert folder.name == "2026-10-05 - Feature Discussion"


def test_save_meeting_writes_transcript_and_metadata(tmp_path):
    folder = save_meeting(_metadata(), _transcript(), meetings_dir=tmp_path)
    assert (folder / "transcript.json").exists()
    assert (folder / "metadata.json").exists()
    assert not (folder / "meeting.md").exists()


def test_save_meeting_with_markdown(tmp_path):
    transcript = _transcript()
    markdown = render_markdown(StructuredMeetingData(title="X"), _metadata(), transcript)
    folder = save_meeting(
        _metadata(), transcript, markdown=markdown, meetings_dir=tmp_path
    )
    assert (folder / "meeting.md").read_text(encoding="utf-8") == markdown


def test_raw_transcript_preserved_after_intelligence(tmp_path):
    transcript = _transcript()
    before = json.dumps(transcript.to_dict(), ensure_ascii=False, indent=2)
    folder = save_meeting(
        _metadata(),
        transcript,
        markdown="# Meeting\n",
        structured=StructuredMeetingData(title="X"),
        meetings_dir=tmp_path,
    )
    after = (folder / "transcript.json").read_text(encoding="utf-8")
    assert after == before


def test_list_meetings_newest_first(tmp_path):
    m1 = MeetingMetadata(meeting_id="a", title="Older", date="2026-01-01")
    m2 = MeetingMetadata(meeting_id="b", title="Newer", date="2026-02-01")
    save_meeting(m1, _transcript(), meetings_dir=tmp_path)
    save_meeting(m2, _transcript(), meetings_dir=tmp_path)
    names = [p.name for p in list_meetings(tmp_path)]
    assert names == ["2026-02-01 - Newer", "2026-01-01 - Older"]

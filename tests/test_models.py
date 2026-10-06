"""Tests for data-model round-trips."""

from __future__ import annotations

from ai.models.transcript import (
    ActionItem,
    Decision,
    StructuredMeetingData,
    Transcript,
    TranscriptSegment,
)


def test_transcript_round_trip():
    transcript = Transcript(
        meeting_id="m1",
        started_at="2026-10-05T10:00:00Z",
        provider="gemini",
        model="test-model",
        segments=[
            TranscriptSegment("segment_001", "Speaker 1", 0.0, 2.0, "Hello.", "english"),
            TranscriptSegment("segment_002", "Speaker 2", 2.0, 4.0, "হ্যাঁ।", "bangla"),
        ],
    )
    restored = Transcript.from_dict(transcript.to_dict())
    assert restored.to_dict() == transcript.to_dict()


def test_structured_round_trip():
    data = StructuredMeetingData(
        title="T",
        summary="S",
        decisions=[Decision(text="D")],
        action_items=[ActionItem(text="A", owner="Efti"), ActionItem(text="B")],
    )
    restored = StructuredMeetingData.from_dict(data.to_dict())
    assert restored.to_dict() == data.to_dict()


def test_meeting_metadata_from_dict_ignores_unknown_keys():
    from ai.models.transcript import MeetingMetadata

    data = {
        "meeting_id": "m1",
        "title": "T",
        "date": "2026-10-06",
        "structured": {"summary": "should be ignored, not crash"},
    }
    metadata = MeetingMetadata.from_dict(data)
    assert metadata.meeting_id == "m1"
    assert metadata.title == "T"


def test_next_segment_id_increments():
    transcript = Transcript(meeting_id="m1")
    assert transcript.next_segment_id() == "segment_001"
    transcript.add_segment(TranscriptSegment("segment_001", "Speaker 1", 0, 1, "x"))
    assert transcript.next_segment_id() == "segment_002"

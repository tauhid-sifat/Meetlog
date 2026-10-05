"""Tests for the deterministic Markdown renderer."""

from __future__ import annotations

from ai.models.transcript import (
    ActionItem,
    Decision,
    DiscussionTopic,
    ImportantDate,
    MeetingMetadata,
    OpenQuestion,
    StructuredMeetingData,
    Transcript,
    TranscriptSegment,
)
from ai.render.markdown import render_markdown


def _metadata() -> MeetingMetadata:
    return MeetingMetadata(
        meeting_id="m1",
        title="Feature Discussion",
        date="2026-10-05",
        duration_seconds=2520,
        mode="online",
        participants=["Tauhid", "Constance", "Efti"],
    )


def _full_data() -> StructuredMeetingData:
    return StructuredMeetingData(
        title="Feature Discussion",
        summary="The team reviewed scope and agreed to move the feature.",
        decisions=[Decision(text="Move the feature to the next sprint.")],
        action_items=[
            ActionItem(text="Confirm backend scope", owner="Efti"),
            ActionItem(text="Update documentation"),
        ],
        open_questions=[OpenQuestion(text="Is UI work in the following sprint?")],
        important_dates=[ImportantDate(text="Sprint planning", date="2026-10-08")],
        discussion_topics=[
            DiscussionTopic(title="Feature Scope", points=["Reduce v1 scope."]),
        ],
    )


def _transcript() -> Transcript:
    return Transcript(
        meeting_id="m1",
        segments=[
            TranscriptSegment("segment_001", "Speaker 1", 0.0, 2.0, "Hello there."),
            TranscriptSegment(
                "segment_002", "Speaker 2", 2.0, 4.0, "হ্যাঁ, agreed.", "mixed"
            ),
        ],
    )


def test_rendering_is_deterministic():
    data, meta = _full_data(), _metadata()
    first = render_markdown(data, meta, _transcript())
    second = render_markdown(data, meta, _transcript())
    assert first == second


def test_header_block_contains_metadata():
    text = render_markdown(_full_data(), _metadata(), _transcript())
    assert text.startswith("# Meeting: Feature Discussion")
    assert "**Date:** October 5, 2026" in text
    assert "**Duration:** 42 minutes" in text
    assert "**Mode:** Online" in text
    assert "**Participants:** Tauhid, Constance, Efti" in text


def test_empty_sections_are_omitted():
    data = StructuredMeetingData(title="Empty", summary="Only a summary.")
    text = render_markdown(data, _metadata())
    assert "## Summary" in text
    for heading in (
        "## Discussion",
        "## Decisions",
        "## Action Items",
        "## Open Questions",
        "## Important Dates",
        "## Full Transcript",
    ):
        assert heading not in text


def test_action_items_render_owner_and_checkbox():
    text = render_markdown(_full_data(), _metadata())
    assert "- [ ] Efti: Confirm backend scope" in text
    assert "- [ ] Update documentation" in text


def test_transcript_grouped_by_speaker():
    text = render_markdown(_full_data(), _metadata(), _transcript())
    assert "## Full Transcript" in text
    assert "### Speaker 1" in text
    assert "### Speaker 2" in text
    assert "হ্যাঁ, agreed." in text


def test_bangla_is_preserved_not_translated():
    text = render_markdown(_full_data(), _metadata(), _transcript())
    assert "হ্যাঁ" in text

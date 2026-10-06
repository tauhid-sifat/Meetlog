"""Phase 6 renderer tests: Requirements + Risks sections and templates."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai.models.transcript import (
    ActionItem,
    Decision,
    MeetingMetadata,
    Requirement,
    Risk,
    StructuredMeetingData,
    Transcript,
    TranscriptSegment,
)
from ai.render.markdown import render_markdown
from ai.render.templates import render_with_template

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"


def _metadata() -> MeetingMetadata:
    return MeetingMetadata(
        meeting_id="m1",
        title="Phase Six",
        date="2026-10-05",
        duration_seconds=1500,
        mode="online",
        participants=["Tauhid", "Efti"],
    )


def _data_with_new_sections() -> StructuredMeetingData:
    return StructuredMeetingData(
        title="Phase Six",
        summary="Summary here.",
        decisions=[Decision(text="Ship it.")],
        action_items=[
            ActionItem(text="Confirm backend scope", owner="Efti"),
            ActionItem(text="Update documentation"),
        ],
        requirements=[Requirement(text="Support offline export.")],
        risks=[Risk(text="Vendor API may rate-limit us.")],
        open_questions=[],
        important_dates=[],
        discussion_topics=[],
    )


def _transcript() -> Transcript:
    return Transcript(
        meeting_id="m1",
        segments=[
            TranscriptSegment("segment_001", "Speaker 1", 0.0, 1.0, "Hello."),
            TranscriptSegment("segment_002", "Speaker 2", 1.0, 2.0, "Hi back."),
        ],
    )


def test_requirements_render_when_present():
    text = render_markdown(_data_with_new_sections(), _metadata())
    assert "## Requirements" in text
    assert "- Support offline export." in text
    # Requirements come after Action Items and before Risks.
    assert text.index("## Action Items") < text.index("## Requirements")
    assert text.index("## Requirements") < text.index("## Risks")


def test_risks_render_when_present():
    text = render_markdown(_data_with_new_sections(), _metadata())
    assert "## Risks" in text
    assert "- Vendor API may rate-limit us." in text


def test_requirements_and_risks_omitted_when_empty():
    data = StructuredMeetingData(title="Empty", summary="Only a summary.")
    text = render_markdown(data, _metadata())
    assert "## Requirements" not in text
    assert "## Risks" not in text


def test_blank_requirement_and_risk_text_skipped():
    data = StructuredMeetingData(
        title="T",
        summary="S",
        requirements=[Requirement(text="   ")],
        risks=[Risk(text="")],
    )
    text = render_markdown(data, _metadata())
    bullets = [line for line in text.splitlines() if line.startswith("- ")]
    assert bullets == []


def test_render_deterministic_including_new_sections():
    data = _data_with_new_sections()
    first = render_markdown(data, _metadata(), _transcript())
    second = render_markdown(data, _metadata(), _transcript())
    assert first == second


def test_owner_formatting_unchanged():
    text = render_markdown(_data_with_new_sections(), _metadata())
    assert "- [ ] Efti: Confirm backend scope" in text
    assert "- [ ] Update documentation" in text


def test_default_template_mirrors_deterministic_renderer():
    data = _data_with_new_sections()
    expected = render_markdown(data, _metadata(), _transcript())
    actual = render_with_template(
        data, _metadata(), _transcript(), TEMPLATES_DIR / "meeting.md.j2"
    )
    assert actual == expected


def test_custom_template_is_slimmer():
    data = _data_with_new_sections()
    text = render_with_template(
        data, _metadata(), _transcript(), TEMPLATES_DIR / "custom.md.j2"
    )
    assert "## Decisions" in text
    assert "## Action Items" in text
    assert "## Requirements" not in text
    assert "## Risks" not in text
    assert "## Full Transcript" not in text
    assert "## Summary" in text


def test_missing_template_raises_filenotfound():
    with pytest.raises(FileNotFoundError):
        render_with_template(
            _data_with_new_sections(),
            _metadata(),
            None,
            TEMPLATES_DIR / "does-not-exist.md.j2",
        )

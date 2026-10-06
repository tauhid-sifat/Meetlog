"""Phase 6 intelligence upgrade — offline tests only (no network, no API key)."""

from __future__ import annotations

import asyncio
import json

import pytest

from ai.intelligence.gemini import GeminiIntelligenceProvider
from ai.models.transcript import StructuredMeetingData, Transcript, TranscriptSegment


def _sample_transcript() -> Transcript:
    return Transcript(
        meeting_id="m1",
        segments=[
            TranscriptSegment(
                id="segment_001",
                speaker="Alice",
                start=1.5,
                end=3.0,
                text="We agreed to launch on Friday.",
            ),
            TranscriptSegment(
                id="segment_002",
                speaker="Bob",
                start=3.0,
                end=5.25,
                text="Rahim will send the report.",
            ),
        ],
    )


def test_render_prompt_includes_speaker_labels_and_timestamps():
    prompt = GeminiIntelligenceProvider._render_prompt(_sample_transcript())
    assert "Alice" in prompt
    assert "Bob" in prompt
    # Timestamps rendered as [start-end] ranges.
    assert "1.50" in prompt
    assert "3.00" in prompt
    assert "5.25" in prompt
    assert "We agreed to launch on Friday." in prompt


def test_parse_json_with_requirements_risks_and_fences():
    payload = {
        "title": "Sync",
        "summary": "Team discussed launch.",
        "decisions": [{"text": "Launch on Friday"}],
        "action_items": [{"text": "Send report", "owner": "Rahim"}],
        "requirements": [{"text": "Must support offline mode"}],
        "risks": [{"text": "Server might break under load"}],
        "open_questions": [],
        "important_dates": [],
        "discussion_topics": [],
    }
    fenced = "```json\n" + json.dumps(payload) + "\n```"
    parsed = GeminiIntelligenceProvider._parse_json(fenced)
    assert parsed["title"] == "Sync"
    data = StructuredMeetingData.from_dict(parsed)
    assert len(data.requirements) == 1
    assert data.requirements[0].text == "Must support offline mode"
    assert len(data.risks) == 1
    assert data.risks[0].text == "Server might break under load"
    assert len(data.decisions) == 1
    assert len(data.action_items) == 1


def test_parse_json_raises_on_invalid_json():
    with pytest.raises(ValueError):
        GeminiIntelligenceProvider._parse_json("{not valid json")


def test_from_dict_maps_requirements_risks():
    data = StructuredMeetingData.from_dict(
        {
            "title": "T",
            "requirements": [{"text": "req1"}, {"text": "req2"}],
            "risks": [{"text": "risk1"}],
        }
    )
    assert [r.text for r in data.requirements] == ["req1", "req2"]
    assert [r.text for r in data.risks] == ["risk1"]


def test_from_dict_backward_compat_defaults_to_empty():
    data = StructuredMeetingData.from_dict({"title": "Old payload"})
    assert data.requirements == []
    assert data.risks == []
    # Round-trip stays backward compatible.
    assert data.to_dict()["requirements"] == []
    assert data.to_dict()["risks"] == []


def test_process_transcript_empty_returns_meeting_without_api():
    provider = object.__new__(GeminiIntelligenceProvider)

    async def _fail_if_called(_prompt: str):  # pragma: no cover
        raise AssertionError("API must not be called for empty transcript")

    provider._generate_with_retry = _fail_if_called  # type: ignore[attr-defined]
    result = asyncio.run(
        provider.process_transcript(Transcript(meeting_id="m-empty"))
    )
    assert isinstance(result, StructuredMeetingData)
    assert result.title == "Meeting"

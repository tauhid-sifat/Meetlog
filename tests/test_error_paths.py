"""Error-path tests: constructors reject missing keys, tolerant parsing,
safe rendering, filename sanitizing, speaker-rename validation, and
language-detection fallbacks. All offline, no network, no API key."""

from __future__ import annotations

import json

import pytest

from ai.intelligence.gemini import GeminiIntelligenceProvider
from ai.main import SidecarSession, detect_language
from ai.models.transcript import MeetingMetadata, StructuredMeetingData
from ai.render.markdown import render_markdown
from ai.storage.transcript import sanitize_name
from ai.stt.gemini import GeminiLiveProvider


def test_live_provider_rejects_empty_key():
    with pytest.raises(ValueError):
        GeminiLiveProvider("")


def test_intelligence_provider_rejects_empty_key():
    with pytest.raises(ValueError):
        GeminiIntelligenceProvider("")


def test_from_dict_tolerates_empty_dict():
    data = StructuredMeetingData.from_dict({})
    assert data.title == "Meeting"
    assert data.summary == ""
    assert data.decisions == []
    assert data.action_items == []


def test_from_dict_tolerates_missing_keys():
    data = StructuredMeetingData.from_dict({"title": "Sync"})
    assert data.title == "Sync"
    assert data.summary == ""
    assert data.discussion_topics == []


def test_render_empty_data_has_meeting_heading():
    text = render_markdown(
        StructuredMeetingData(),
        MeetingMetadata(meeting_id="m1", title="Meeting", date="2026-10-06"),
    )
    assert text
    assert "# Meeting" in text


def test_sanitize_name_strips_windows_invalid_chars():
    cleaned = sanitize_name('a<b>c:d"e/f\\g|h?i*j')
    for ch in '<>:"/\\|?*':
        assert ch not in cleaned
    assert cleaned


class _FakeWriter:
    """Minimal writer for SidecarSession: write(bytes) + async drain()."""

    def __init__(self) -> None:
        self.chunks: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.chunks.append(data)

    async def drain(self) -> None:
        return None

    def events(self) -> list[dict]:
        return [json.loads(c.decode("utf-8")) for c in self.chunks]


async def _rename_empty() -> tuple[bool, list[dict]]:
    writer = _FakeWriter()
    session = SidecarSession(writer)  # type: ignore[arg-type]
    result = await session.rename_speaker("Speaker 1", "")
    return result, writer.events()


def test_rename_speaker_empty_name_fails_with_error_event():
    import asyncio

    result, events = asyncio.run(_rename_empty())
    assert result is False
    assert events
    assert events[-1].get("type") == "error"


def test_detect_language_unknown_for_digits():
    assert detect_language("123 456", None) == "unknown"


def test_detect_language_hindi_and_japanese():
    assert detect_language("कैसे हो, ठीक हो?", None) == "hindi"
    assert detect_language("こんにちは", None) == "japanese"

"""Tests for speaker renaming in the sidecar session."""

from __future__ import annotations

import asyncio
import json

from ai.main import SidecarSession, normalize_speaker, resolve_speaker
from ai.models.transcript import TranscriptSegment


class FakeWriter:
    def __init__(self) -> None:
        self.lines: list[dict] = []

    def write(self, data: bytes) -> None:
        self.lines.append(json.loads(data.decode("utf-8")))

    async def drain(self) -> None:
        return None


def _session_with(*speakers: str) -> tuple[SidecarSession, FakeWriter]:
    writer = FakeWriter()
    session = SidecarSession(writer)  # type: ignore[arg-type]
    for i, speaker in enumerate(speakers):
        session._transcript.add_segment(
            TranscriptSegment(
                id=f"segment_{i + 1:03d}",
                speaker=speaker,
                start=float(i),
                end=float(i + 1),
                text=f"line {i}",
            )
        )
    return session, writer


def test_resolve_speaker_applies_mapping():
    assert resolve_speaker("Speaker 1", {"Speaker 1": "Tauhid"}) == "Tauhid"
    assert resolve_speaker("Speaker 2", {"Speaker 1": "Tauhid"}) == "Speaker 2"
    assert resolve_speaker(None, None) == "Speaker 1"


def test_rename_rewrites_past_segments_and_announces():
    session, writer = _session_with("Speaker 1", "Speaker 2", "Speaker 1")
    assert asyncio.run(session.rename_speaker("Speaker 1", "Tauhid")) is True

    assert [s.speaker for s in session._transcript.segments] == [
        "Tauhid",
        "Speaker 2",
        "Tauhid",
    ]
    assert session.speakers() == ["Tauhid", "Speaker 2"]
    assert writer.lines[-1] == {
        "type": "speakers",
        "speakers": ["Tauhid", "Speaker 2"],
    }


def test_rename_chains_through_display_names():
    session, _ = _session_with("Speaker 1")
    assert asyncio.run(session.rename_speaker("Speaker 1", "Tauhid")) is True
    assert asyncio.run(session.rename_speaker("Tauhid", "T")) is True
    assert [s.speaker for s in session._transcript.segments] == ["T"]
    assert session.speakers() == ["T"]


def test_rename_is_case_insensitive():
    session, _ = _session_with("Speaker 1")
    assert asyncio.run(session.rename_speaker("speaker 1", "Tauhid")) is True
    assert session.speakers() == ["Tauhid"]


def test_rename_rejects_empty_name():
    session, writer = _session_with("Speaker 1")
    assert asyncio.run(session.rename_speaker("Speaker 1", "   ")) is False
    assert [s.speaker for s in session._transcript.segments] == ["Speaker 1"]
    assert writer.lines[-1]["type"] == "error"


def test_rename_rejects_unknown_speaker():
    session, writer = _session_with("Speaker 1")
    assert asyncio.run(session.rename_speaker("Speaker 9", "Nadia")) is False
    assert session._speaker_names == {}
    assert writer.lines[-1] == {"type": "error", "message": "unknown speaker: Speaker 9"}


def test_rename_without_segments_reports_unknown():
    writer = FakeWriter()
    session = SidecarSession(writer)  # type: ignore[arg-type]
    assert asyncio.run(session.rename_speaker("Speaker 1", "Tauhid")) is False


def test_stop_records_participants(monkeypatch, tmp_path):
    import ai.main as main

    saved: dict = {}

    def fake_save(metadata, transcript, **kwargs):
        saved["participants"] = list(metadata.participants)
        return tmp_path / "meeting"

    monkeypatch.setattr(main, "save_meeting", fake_save)

    async def scenario() -> dict:
        session, _ = _session_with("Speaker 1", "Speaker 2")
        session._metadata = None
        from ai.models.transcript import MeetingMetadata

        session._metadata = MeetingMetadata(
            meeting_id="m1", title="T", date="2026-10-06"
        )
        assert await session.rename_speaker("Speaker 1", "Tauhid") is True
        await session.stop({"generate_markdown": False})
        return saved

    result = asyncio.run(scenario())
    assert result["participants"] == ["Tauhid", "Speaker 2"]
    assert normalize_speaker("2") == "Speaker 2"

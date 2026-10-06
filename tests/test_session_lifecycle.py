"""Tests for meeting lifecycle: session reset, stop metadata, failure handling."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from ai.main import SidecarSession
from ai.models.transcript import MeetingMetadata, TranscriptSegment


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


def _metered(session: SidecarSession) -> None:
    session._metadata = MeetingMetadata(meeting_id="m1", title="T", date="2026-10-06")
    session._started_at = datetime.now(timezone.utc)


def test_start_reset_clears_previous_meeting():
    async def scenario() -> None:
        session, _ = _session_with("Speaker 1", "Speaker 2")
        old_id = session._transcript.meeting_id
        session._speaker_names = {"Speaker 1": "Tauhid"}
        session._stopping = True
        session._audio_chunks = 7
        _metered(session)
        await session._reset_for_new_meeting()
        assert session._transcript.segments == []
        assert session._transcript.meeting_id != old_id
        assert session._speaker_names == {}
        assert session._metadata is None
        assert session._started_at is None
        assert session._stopping is False
        assert session._audio_chunks == 0
        assert session._audio_bytes == 0
        assert session._audio_by_source == {}

    asyncio.run(scenario())


def test_stop_sets_ended_at_participants_and_folder(monkeypatch, tmp_path):
    import ai.main as main

    monkeypatch.setattr(main, "save_meeting", lambda *a, **k: tmp_path / "meeting")

    async def scenario() -> tuple[dict, SidecarSession]:
        session, writer = _session_with("Speaker 1", "Speaker 2")
        _metered(session)
        assert await session.rename_speaker("Speaker 1", "Tauhid") is True
        writer.lines.clear()
        await session.stop({"generate_markdown": False})
        stopped = [m for m in writer.lines if m["type"] == "stopped"]
        assert len(stopped) == 1
        return stopped[0], session

    stopped, session = asyncio.run(scenario())
    assert stopped["folder"] == str(tmp_path / "meeting")
    assert stopped["markdown_path"] is None
    assert session._metadata is not None
    assert session._metadata.ended_at is not None
    assert session._metadata.participants == ["Tauhid", "Speaker 2"]


def test_stop_keeps_folder_when_intelligence_fails(monkeypatch, tmp_path):
    import ai.main as main

    monkeypatch.setattr(main, "save_meeting", lambda *a, **k: tmp_path / "meeting")

    async def boom(*a, **k):
        raise RuntimeError("LLM overloaded")

    monkeypatch.setattr(main, "generate_meeting", boom)

    async def scenario() -> list[dict]:
        session, writer = _session_with("Speaker 1")
        _metered(session)
        await session.stop({"generate_markdown": True, "api_key": "k"})
        return writer.lines

    lines = asyncio.run(scenario())
    errors = [m for m in lines if m["type"] == "error"]
    stopped = [m for m in lines if m["type"] == "stopped"]
    assert any("generation failed" in m["message"] for m in errors)
    assert len(stopped) == 1
    assert stopped[0]["folder"] == str(tmp_path / "meeting")
    assert stopped[0]["markdown_path"] is None

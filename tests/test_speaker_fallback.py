"""Tests for source-activity fallback speaker attribution."""

from __future__ import annotations

import asyncio
import struct

from ai.main import SidecarSession, resolve_speaker
from ai.models.transcript import MeetingMetadata


class FakeWriter:
    def __init__(self) -> None:
        self.lines: list[dict] = []

    def write(self, data: bytes) -> None:
        import json

        self.lines.append(json.loads(data.decode("utf-8")))

    async def drain(self) -> None:
        return None


def _session(mode: str = "online") -> SidecarSession:
    session = SidecarSession(FakeWriter())  # type: ignore[arg-type]
    session._metadata = MeetingMetadata(meeting_id="m1", title="T", date="2026-10-06")
    session._metadata.mode = mode
    return session


def _pcm(amplitude: int, chunks: int = 10) -> bytes:
    """Synthesize `chunks` 100 ms blocks of constant-amplitude mono int16 PCM."""
    block = struct.pack("<1600h", *([amplitude] * 1600))
    return block * chunks


def _feed(session: SidecarSession, mic_amp: int, sys_amp: int) -> None:
    session._note_activity("mic", _pcm(mic_amp))
    session._note_activity("system", _pcm(sys_amp))


def test_model_label_wins_over_fallback():
    session = _session("online")
    _feed(session, mic_amp=0, sys_amp=8000)
    assert session._speaker_for("Speaker 3") == "Speaker 3"


def test_mic_dominant_attributes_you():
    session = _session("online")
    _feed(session, mic_amp=8000, sys_amp=0)
    assert session._speaker_for(None) == "You"


def test_system_dominant_attributes_guest():
    session = _session("online")
    _feed(session, mic_amp=0, sys_amp=8000)
    assert session._speaker_for(None) == "Guest"


def test_silence_falls_back_to_speaker_1():
    session = _session("online")
    _feed(session, mic_amp=0, sys_amp=0)
    assert session._speaker_for(None) == "Speaker 1"


def test_contested_window_falls_back_to_speaker_1():
    session = _session("online")
    _feed(session, mic_amp=8000, sys_amp=8000)
    assert session._speaker_for(None) == "Speaker 1"


def test_offline_ignores_source_activity():
    session = _session("offline")
    _feed(session, mic_amp=0, sys_amp=8000)
    assert session._speaker_for(None) == "Speaker 1"


def test_fallback_label_follows_rename():
    from ai.models.transcript import TranscriptSegment

    async def scenario() -> None:
        session = _session("online")
        _feed(session, mic_amp=8000, sys_amp=0)
        assert session._speaker_for(None) == "You"
        # A fallback-attributed segment lands in the transcript, as in _handle_event.
        session._transcript.add_segment(
            TranscriptSegment(
                id="segment_001",
                speaker="You",
                start=0.0,
                end=1.0,
                text="hello",
            )
        )
        assert await session.rename_speaker("You", "Tauhid") is True
        # Later segments with no model label must stay renamed.
        _feed(session, mic_amp=8000, sys_amp=0)
        assert session._speaker_for(None) == "Tauhid"

    asyncio.run(scenario())


def test_activity_window_is_bounded():
    session = _session("online")
    for _ in range(4000):
        session._note_activity("mic", _pcm(100, chunks=1))
    assert len(session._activity) <= 3600


def test_provider_defaults_diarization_on():
    from ai.stt.gemini import GeminiLiveProvider

    assert GeminiLiveProvider("dummy-key")._diarization is True


def test_resolve_speaker_passthrough():
    assert resolve_speaker(None, None) == "Speaker 1"
    assert resolve_speaker("5", None) == "Speaker 5"

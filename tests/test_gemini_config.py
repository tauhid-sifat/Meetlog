"""Tests for Gemini Live provider configuration building."""

from __future__ import annotations

from ai.stt.gemini import GeminiLiveProvider


def _provider(**kwargs) -> GeminiLiveProvider:
    return GeminiLiveProvider("dummy-key", **kwargs)


def test_language_hints_wrapped_in_object():
    provider = _provider(language_hints=["en-US"])
    config = provider._build_config()
    hints = config.input_audio_transcription.language_hints
    assert hints is not None
    assert hints.language_codes == ["en-US"]


def test_no_language_hints_is_none():
    provider = _provider()
    config = provider._build_config()
    assert config.input_audio_transcription.language_hints is None


def test_custom_vocabulary_and_language_codes_pass_through():
    provider = _provider(
        language_codes=["bn-BD"], custom_vocabulary=["FortiMapp", "Caboodle"]
    )
    config = provider._build_config()
    assert config.input_audio_transcription.language_codes == ["bn-BD"]
    assert config.input_audio_transcription.custom_vocabulary == [
        "FortiMapp",
        "Caboodle",
    ]


def test_system_instruction_and_mode():
    provider = _provider(system_instruction="be exact", mode="SMART", diarization=True)
    config = provider._build_config()
    assert config.system_instruction == "be exact"
    assert config.input_audio_transcription.mode.value == "SMART"
    assert config.input_audio_transcription.diarization is True

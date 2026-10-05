"""Tests for language detection and speaker normalization."""

from __future__ import annotations

from ai.main import detect_language, normalize_speaker


def test_bangla_detected():
    assert detect_language("আমাদের এটা করতে হবে", "bn-BD") == "bangla"


def test_english_detected():
    assert detect_language("We should finalize this", "en-US") == "english"


def test_mixed_detected():
    assert detect_language("আমাদের Thursday-এর মধ্যে finalize করতে হবে", None) == "mixed"


def test_code_fallback_for_other_scripts():
    assert detect_language("こんにちは", "ja-JP") == "ja-jp"


def test_unknown_when_no_letters():
    assert detect_language("123 456", None) == "unknown"


def test_normalize_speaker():
    assert normalize_speaker(None) == "Speaker 1"
    assert normalize_speaker("2") == "Speaker 2"
    assert normalize_speaker("Constance") == "Constance"

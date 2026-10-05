"""Shared configuration for the Meetlog AI sidecar.

All values can be overridden with environment variables so the Tauri layer can
pass provider/model choices through without code changes.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Audio pipeline constants -------------------------------------------------
# Gemini Live accepts raw 16-bit little-endian PCM at 16 kHz, mono.
SAMPLE_RATE = 16_000
CHANNELS = 1
SAMPLE_WIDTH = 2  # bytes per sample (int16)
CHUNK_MS = 100
CHUNK_BYTES = SAMPLE_RATE * SAMPLE_WIDTH * CHUNK_MS // 1000  # 3200 bytes / 100 ms

# --- Gemini provider defaults -------------------------------------------------
# The live transcription model and the batch LLM used for meeting intelligence.
GEMINI_LIVE_MODEL = os.environ.get(
    "MEETLOG_GEMINI_LIVE_MODEL", "gemini-3.5-transcribe-live"
)
GEMINI_LLM_MODEL = os.environ.get("MEETLOG_GEMINI_LLM_MODEL", "gemini-2.5-flash")
GEMINI_API_KEY_ENV = "GEMINI_API_KEY"

# Gemini Live sessions are capped at 10 minutes; rotate a little before that.
SESSION_MAX_SECONDS = float(os.environ.get("MEETLOG_SESSION_MAX_SECONDS", "540"))

# Transcription mode: VERBATIM preserves the words; SMART cleans filler/format.
TRANSCRIPTION_MODE = os.environ.get("MEETLOG_TRANSCRIPTION_MODE", "VERBATIM")

# --- Storage ------------------------------------------------------------------
DEFAULT_MEETINGS_DIR = Path(
    os.environ.get(
        "MEETLOG_MEETINGS_DIR", str(Path.home() / "Meetlog" / "Meetings")
    )
)

# --- TCP sidecar protocol -----------------------------------------------------
SIDECAR_HOST = "127.0.0.1"


def api_key() -> str | None:
    """Return the configured Gemini API key, or None if unset."""
    return os.environ.get(GEMINI_API_KEY_ENV) or None

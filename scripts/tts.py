"""Shared Gemini TTS helper for the validation scripts."""

from __future__ import annotations

import os
import re
import wave
from pathlib import Path

from google import genai
from google.genai import types

TTS_MODEL = os.environ.get("MEETLOG_TTS_MODEL", "gemini-2.5-flash-preview-tts")


def write_wav(
    path: Path, pcm: bytes, rate: int, channels: int = 1, width: int = 2
) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(rate)
        wav.writeframes(pcm)


def synthesize(
    client: genai.Client, text: str, out_path: Path, voice: str = "Kore"
) -> Path:
    """Synthesize ``text`` to a WAV file and return its path."""
    response = client.models.generate_content(
        model=TTS_MODEL,
        contents=text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                )
            ),
        ),
    )
    part = response.candidates[0].content.parts[0]
    inline = part.inline_data
    if inline is None or inline.data is None:
        raise RuntimeError("TTS returned no audio")
    rate_match = re.search(r"rate=(\d+)", inline.mime_type or "")
    rate = int(rate_match.group(1)) if rate_match else 24000
    write_wav(out_path, inline.data, rate)
    return out_path

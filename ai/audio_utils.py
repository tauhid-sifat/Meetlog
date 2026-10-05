"""Audio helpers shared by the CLI harness and the benchmark."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from ai.config import SAMPLE_RATE


def read_wav_mono_16k(path: Path | str) -> bytes:
    """Read a WAV file and return 16 kHz mono int16 little-endian PCM bytes.

    Multi-channel audio is mixed to mono; other sample rates are linearly
    resampled to 16 kHz. Raises ValueError for non-16-bit PCM WAVs.
    """
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        width = wav.getsampwidth()
        frame_rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())

    if width != 2:
        raise ValueError(
            f"expected 16-bit PCM WAV, got {width * 8}-bit; convert the file first"
        )

    samples = np.frombuffer(frames, dtype="<i2")
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1).astype(np.int16)

    if frame_rate != SAMPLE_RATE:
        samples = _resample(samples.astype(np.float32), frame_rate, SAMPLE_RATE)
        samples = np.clip(samples, -32768, 32767).astype("<i2")

    return samples.astype("<i2").tobytes()


def _resample(samples: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    if orig_sr == target_sr or samples.size == 0:
        return samples
    duration = samples.shape[0] / orig_sr
    target_len = int(round(duration * target_sr))
    x_old = np.linspace(0.0, duration, num=samples.shape[0], endpoint=False)
    x_new = np.linspace(0.0, duration, num=target_len, endpoint=False)
    return np.interp(x_new, x_old, samples).astype(np.float32)


def chunk_pcm(pcm: bytes, chunk_bytes: int) -> list[bytes]:
    """Split PCM bytes into fixed-size chunks (last chunk may be short)."""
    return [pcm[i : i + chunk_bytes] for i in range(0, len(pcm), chunk_bytes)]

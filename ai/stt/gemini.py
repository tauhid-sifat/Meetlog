"""Gemini Live speech-to-text provider.

Uses the Gemini Live API (``gemini-3.5-transcribe-live`` by default) for
low-latency streaming transcription with automatic language detection,
code-switching, custom vocabulary, and optional speaker diarization.

The provider transparently rotates the underlying WebSocket session before the
API's 10-minute cap so long meetings keep transcribing without interruption:
before rotating it asks the model to flush final transcripts, and any audio
captured during the reconnect window is buffered and replayed into the new
session so nothing is lost.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator

from google import genai
from google.genai import types

from ai.config import (
    GEMINI_LIVE_MODEL,
    SESSION_MAX_SECONDS,
    TRANSCRIPTION_MODE,
)
from ai.models.transcript import TranscriptEvent
from ai.stt.base import STTProvider

_SENTINEL = object()
_AUDIO_MIME = "audio/pcm;rate=16000"


class GeminiLiveProvider(STTProvider):
    """Streaming STT backed by the Gemini Live API."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = GEMINI_LIVE_MODEL,
        language_codes: list[str] | None = None,
        language_hints: list[str] | None = None,
        custom_vocabulary: list[str] | None = None,
        system_instruction: str | None = None,
        mode: str = TRANSCRIPTION_MODE,
        diarization: bool = False,
        session_max_seconds: float = SESSION_MAX_SECONDS,
        response_modalities: list[str] | None = None,
        max_consecutive_errors: int = 5,
        connect_timeout: float = 15.0,
        flush_wait_seconds: float = 1.5,
    ) -> None:
        if not api_key:
            raise ValueError("GeminiLiveProvider requires an API key")

        self._api_key = api_key
        self._model = model or GEMINI_LIVE_MODEL
        self._language_codes = list(language_codes or [])
        self._language_hints = list(language_hints or [])
        self._custom_vocabulary = list(custom_vocabulary or [])
        self._system_instruction = system_instruction
        self._mode = mode
        self._diarization = diarization
        self._session_max_seconds = session_max_seconds
        self._response_modalities = response_modalities or ["TEXT"]
        self._max_consecutive_errors = max_consecutive_errors
        self._connect_timeout = connect_timeout
        self._flush_wait_seconds = flush_wait_seconds

        self._client: genai.Client | None = None
        self._session: types.AsyncSession | None = None  # type: ignore[name-defined]
        self._events: asyncio.Queue = asyncio.Queue()
        self._supervisor: asyncio.Task | None = None
        self._ready = asyncio.Event()
        self._lock = asyncio.Lock()

        self._started = False
        self._paused = False
        self._stopped = False
        self._rotating = False
        self._pending: list[bytes] = []
        self._max_pending = 300  # ~30s of 100ms chunks
        self._last_error: str | None = None
        self._clock_start = 0.0
        self._pending_start: float | None = None

    # -- configuration ------------------------------------------------------ #
    def _build_config(self) -> types.LiveConnectConfig:
        return types.LiveConnectConfig(
            response_modalities=self._response_modalities,
            system_instruction=self._system_instruction,
            input_audio_transcription=types.AudioTranscriptionConfig(
                language_codes=self._language_codes or None,
                language_hints=(
                    types.LanguageHints(language_codes=self._language_hints)
                    if self._language_hints
                    else None
                ),
                custom_vocabulary=self._custom_vocabulary or None,
                mode=types.AudioTranscriptionConfigMode(self._mode),
                diarization=self._diarization,
            ),
        )

    # -- lifecycle ---------------------------------------------------------- #
    async def connect(self) -> None:
        if self._client is None:
            self._client = genai.Client(api_key=self._api_key)
        self._stopped = False
        self._clock_start = time.monotonic()
        self._ready.clear()
        self._supervisor = asyncio.create_task(
            self._supervise(), name="gemini-live-supervisor"
        )
        # Do not return until the first session is actually open, otherwise the
        # caller's early audio (and stream-end signal) would be dropped.
        try:
            await asyncio.wait_for(self._ready.wait(), timeout=self._connect_timeout)
        except asyncio.TimeoutError as exc:
            detail = f" (last error: {self._last_error})" if self._last_error else ""
            raise RuntimeError(
                "Gemini Live session did not open within "
                f"{self._connect_timeout:.0f}s{detail}"
            ) from exc

    async def _supervise(self) -> None:
        """Keep a live session open, rotating it before the 10-minute cap."""
        consecutive_errors = 0
        while not self._stopped:
            try:
                async with self._client.aio.live.connect(  # type: ignore[union-attr]
                    model=self._model, config=self._build_config()
                ) as session:
                    self._session = session
                    consecutive_errors = 0
                    self._ready.set()
                    self._emit(TranscriptEvent.system("session_connected"))
                    # Replay audio buffered during the rotation window.
                    await self._flush_pending()
                    self._rotating = False
                    rotator = asyncio.create_task(
                        self._rotate_after(session, self._session_max_seconds),
                        name="gemini-live-rotator",
                    )
                    try:
                        async for message in session.receive():
                            self._handle_message(message)
                    finally:
                        rotator.cancel()
                        self._session = None
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - surfaced to the client
                if self._rotating:
                    # Expected: the watchdog closed the session to rotate it.
                    pass
                else:
                    consecutive_errors += 1
                    self._last_error = f"{type(exc).__name__}: {exc}"
                    self._emit(TranscriptEvent.error(self._last_error))
                    if consecutive_errors >= self._max_consecutive_errors:
                        self._emit(
                            TranscriptEvent.error(
                                "Gemini Live: too many consecutive failures, giving up"
                            )
                        )
                        break
                    await asyncio.sleep(min(2 ** consecutive_errors, 10))
                    continue
            # Brief pause so the old socket fully closes before reconnecting.
            if not self._stopped:
                await asyncio.sleep(0.2)

    async def _rotate_after(self, session, seconds: float) -> None:
        """Flush finals, then close the session so the supervisor reconnects."""
        try:
            await asyncio.sleep(seconds)
            self._rotating = True
            try:
                await session.send_realtime_input(audio_stream_end=True)
            except Exception:  # noqa: BLE001 - best effort flush
                pass
            await asyncio.sleep(self._flush_wait_seconds)
            await session.close()
        except asyncio.CancelledError:
            pass
        except Exception:  # noqa: BLE001 - supervisor handles reconnection
            pass

    async def _flush_pending(self) -> None:
        async with self._lock:
            pending, self._pending = self._pending, []
            session = self._session
            if session is None:
                self._pending = pending + self._pending
                return
            for i, chunk in enumerate(pending):
                try:
                    await session.send_realtime_input(
                        audio=types.Blob(data=chunk, mime_type=_AUDIO_MIME)
                    )
                except Exception:  # noqa: BLE001 - keep the rest for next time
                    self._pending = pending[i:] + self._pending
                    return

    def _handle_message(self, message) -> None:
        server_content = getattr(message, "server_content", None)
        if server_content is None:
            return

        elapsed = time.monotonic() - self._clock_start

        interim = getattr(server_content, "interim_input_transcription", None)
        if interim is not None and getattr(interim, "text", None):
            if self._pending_start is None:
                self._pending_start = elapsed
            self._emit(
                TranscriptEvent.interim(
                    interim.text,
                    language=getattr(interim, "language_code", None),
                    speaker=getattr(interim, "speaker_label", None),
                )
            )

        final = getattr(server_content, "input_transcription", None)
        if final is not None and getattr(final, "text", None):
            start = self._pending_start if self._pending_start is not None else elapsed
            self._pending_start = None
            self._emit(
                TranscriptEvent.segment(
                    final.text,
                    language=getattr(final, "language_code", None),
                    speaker=getattr(final, "speaker_label", None),
                    start=start,
                    end=elapsed,
                )
            )

    def _emit(self, event: TranscriptEvent) -> None:
        self._events.put_nowait(event)

    async def start(self) -> None:
        self._started = True

    # -- audio -------------------------------------------------------------- #
    async def send_audio(self, pcm: bytes) -> None:
        if self._paused or self._stopped or not pcm:
            return
        if self._rotating:
            self._buffer(pcm)
            return
        async with self._lock:
            session = self._session
            if session is None:
                self._buffer(pcm)
                return
            try:
                await session.send_realtime_input(
                    audio=types.Blob(data=pcm, mime_type=_AUDIO_MIME)
                )
            except Exception:  # noqa: BLE001 - session closed mid-rotation
                self._buffer(pcm)

    def _buffer(self, pcm: bytes) -> None:
        self._pending.append(pcm)
        if len(self._pending) > self._max_pending:
            del self._pending[: len(self._pending) - self._max_pending]

    async def receive_transcript(self) -> AsyncIterator[TranscriptEvent]:
        while not self._stopped:
            event = await self._events.get()
            if event is _SENTINEL:
                break
            yield event

    async def pause(self) -> None:
        self._paused = True

    async def resume(self) -> None:
        self._paused = False

    async def stop(self) -> None:
        """Stop accepting audio and ask the model to flush final transcripts.

        The Live API only finalizes a turn's transcript when it detects silence
        or receives an explicit stream-end signal, so we send one here.
        """
        self._started = False
        session = self._session
        if session is not None:
            try:
                await session.send_realtime_input(audio_stream_end=True)
            except Exception:  # noqa: BLE001 - best effort flush
                pass

    async def disconnect(self) -> None:
        self._stopped = True
        self._events.put_nowait(_SENTINEL)
        if self._supervisor is not None:
            self._supervisor.cancel()
            try:
                await self._supervisor
            except asyncio.CancelledError:
                pass
            self._supervisor = None
        session = self._session
        if session is not None:
            try:
                await session.close()
            except Exception:  # noqa: BLE001
                pass
            self._session = None

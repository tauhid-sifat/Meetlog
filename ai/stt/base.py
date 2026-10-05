"""The STT provider interface.

Every speech-to-text backend implements this interface so the rest of the
application never needs to know which model is being used. Providers are
replaceable without changing the core meeting workflow.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from ai.models.transcript import TranscriptEvent


class STTProvider(ABC):
    """Common interface for interchangeable speech-to-text providers.

    Lifecycle::

        await provider.connect()      # open a session / load the model
        await provider.start()        # begin accepting audio
        await provider.send_audio(b)  # stream 16 kHz mono int16 PCM
        async for event in provider.receive_transcript(): ...
        await provider.pause()        # stop consuming audio (keep session)
        await provider.resume()
        await provider.stop()         # stop accepting audio
        await provider.disconnect()   # release the session / model
    """

    @abstractmethod
    async def connect(self) -> None:
        """Establish the underlying session or load the model."""

    @abstractmethod
    async def start(self) -> None:
        """Begin accepting audio."""

    @abstractmethod
    async def send_audio(self, pcm: bytes) -> None:
        """Send a chunk of raw 16 kHz mono int16 little-endian PCM."""

    @abstractmethod
    def receive_transcript(self) -> AsyncIterator[TranscriptEvent]:
        """Yield transcript events as they are produced."""

    @abstractmethod
    async def pause(self) -> None:
        """Stop consuming audio while keeping the session alive."""

    @abstractmethod
    async def resume(self) -> None:
        """Resume consuming audio after a pause."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop accepting audio (finalize the current session)."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Release the session or model. Safe to call more than once."""

"""The meeting-intelligence provider interface.

Meeting intelligence is independent from speech-to-text. A provider turns a raw
transcript into structured meeting data; it never controls the final Markdown.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ai.models.transcript import StructuredMeetingData, Transcript


class MeetingIntelligenceProvider(ABC):
    """Turns a raw transcript into structured meeting data."""

    @abstractmethod
    async def process_transcript(self, transcript: Transcript) -> StructuredMeetingData:
        """Return structured meeting data extracted from ``transcript``.

        Implementations must not invent decisions, action items, deadlines, or
        requirements that were not discussed.
        """

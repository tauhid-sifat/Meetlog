"""Meeting-intelligence providers."""

from ai.intelligence.base import MeetingIntelligenceProvider
from ai.intelligence.gemini import GeminiIntelligenceProvider

__all__ = ["MeetingIntelligenceProvider", "GeminiIntelligenceProvider"]

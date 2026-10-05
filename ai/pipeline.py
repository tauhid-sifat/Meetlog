"""End-to-end meeting pipeline: transcript -> intelligence -> Markdown -> disk."""

from __future__ import annotations

from pathlib import Path

from ai.config import DEFAULT_MEETINGS_DIR, GEMINI_LLM_MODEL
from ai.intelligence.gemini import GeminiIntelligenceProvider
from ai.models.transcript import MeetingMetadata, StructuredMeetingData, Transcript
from ai.render.markdown import render_markdown
from ai.storage.transcript import save_meeting


async def generate_meeting(
    transcript: Transcript,
    metadata: MeetingMetadata,
    *,
    api_key: str,
    model: str = GEMINI_LLM_MODEL,
    meetings_dir: Path | str = DEFAULT_MEETINGS_DIR,
) -> tuple[str, Path, StructuredMeetingData]:
    """Run meeting intelligence, render Markdown, and persist the meeting.

    Returns ``(markdown_text, meeting_folder, structured_data)``.
    """
    provider = GeminiIntelligenceProvider(api_key, model=model)
    structured = await provider.process_transcript(transcript)
    markdown = render_markdown(structured, metadata, transcript)
    folder = save_meeting(
        metadata,
        transcript,
        markdown=markdown,
        structured=structured,
        meetings_dir=meetings_dir,
    )
    return markdown, folder, structured

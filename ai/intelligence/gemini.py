"""Gemini-backed meeting intelligence.

Sends the raw transcript to a Gemini LLM and returns structured meeting data as
JSON. The model supplies data only; the Markdown renderer controls formatting.
"""

from __future__ import annotations

import json

from google import genai
from google.genai import types

from ai.config import GEMINI_LLM_MODEL
from ai.intelligence.base import MeetingIntelligenceProvider
from ai.models.transcript import StructuredMeetingData, Transcript

_SCHEMA_DESCRIPTION = """{
  "title": "string - a short descriptive meeting title",
  "summary": "string - 2 to 5 sentences",
  "decisions": [{"text": "string"}],
  "action_items": [{"text": "string", "owner": "string or null"}],
  "open_questions": [{"text": "string"}],
  "important_dates": [{"text": "string", "date": "string or null"}],
  "discussion_topics": [{"title": "string", "points": ["string"]}]
}"""

_SYSTEM_INSTRUCTION = f"""You are a precise meeting analyst.

You receive the raw transcript of a meeting and return a single JSON object
matching exactly this schema:

{_SCHEMA_DESCRIPTION}

Hard rules:
- Only include information that is explicitly present in the transcript.
- Never invent decisions, action items, deadlines, owners, or requirements.
- If a section has no information, return an empty array for it.
- Distinguish confirmed information from uncertain discussion; do not promote
  speculation into a decision or action item.
- Preserve the language actually spoken. Do not translate Bangla into English.
  Write the summary in the meeting's dominant language.
- Return only the JSON object, with no surrounding prose or code fences."""


class GeminiIntelligenceProvider(MeetingIntelligenceProvider):
    """Meeting intelligence backed by a Gemini LLM."""

    def __init__(self, api_key: str, *, model: str = GEMINI_LLM_MODEL) -> None:
        if not api_key:
            raise ValueError("GeminiIntelligenceProvider requires an API key")
        self._api_key = api_key
        self._model = model
        self._client = genai.Client(api_key=api_key)

    async def process_transcript(self, transcript: Transcript) -> StructuredMeetingData:
        if not transcript.segments:
            return StructuredMeetingData(title="Meeting")

        prompt = self._render_prompt(transcript)
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )

        text = (response.text or "").strip()
        data = self._parse_json(text)
        return StructuredMeetingData.from_dict(data)

    @staticmethod
    def _render_prompt(transcript: Transcript) -> str:
        lines = []
        for seg in transcript.segments:
            if not seg.text.strip():
                continue
            lines.append(f"[{seg.start:7.2f}-{seg.end:7.2f}] {seg.speaker}: {seg.text}")
        body = "\n".join(lines)
        return f"Meeting transcript:\n\n{body}\n\nReturn the JSON object."

    @staticmethod
    def _parse_json(text: str) -> dict:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Meeting intelligence returned invalid JSON: {exc}"
            ) from exc

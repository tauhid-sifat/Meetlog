"""Deterministic Markdown renderer.

The LLM produces structured data; this module owns the document layout. Given
the same inputs it always produces byte-identical output. Sections with no
meaningful information are omitted.
"""

from __future__ import annotations

from datetime import date as _date

from ai.models.transcript import MeetingMetadata, StructuredMeetingData, Transcript


def _format_duration(seconds: float) -> str:
    total = int(round(seconds))
    if total < 60:
        return f"{total} seconds"
    minutes = total // 60
    if minutes < 60:
        return f"{minutes} minute" + ("s" if minutes != 1 else "")
    hours, rem = divmod(minutes, 60)
    hour_part = f"{hours} hour" + ("s" if hours != 1 else "")
    if rem == 0:
        return hour_part
    return f"{hour_part} {rem} minute" + ("s" if rem != 1 else "")


def _format_date(value: str) -> str:
    try:
        parsed = _date.fromisoformat(value)
        return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"
    except (ValueError, TypeError):
        return value


def render_markdown(
    data: StructuredMeetingData,
    metadata: MeetingMetadata,
    transcript: Transcript | None = None,
) -> str:
    """Render structured meeting data into a Markdown document."""
    lines: list[str] = []

    lines.append(f"# Meeting: {data.title or metadata.title or 'Meeting'}")
    lines.append("")

    if metadata.date:
        lines.append(f"**Date:** {_format_date(metadata.date)}")
    if metadata.duration_seconds:
        lines.append(f"**Duration:** {_format_duration(metadata.duration_seconds)}")
    if metadata.mode:
        lines.append(f"**Mode:** {metadata.mode.capitalize()}")
    if metadata.participants:
        lines.append(f"**Participants:** {', '.join(metadata.participants)}")
    lines.append("")

    if data.summary.strip():
        lines.append("## Summary")
        lines.append("")
        lines.append(data.summary.strip())
        lines.append("")

    if data.discussion_topics:
        lines.append("## Discussion")
        lines.append("")
        for topic in data.discussion_topics:
            if not topic.title.strip():
                continue
            lines.append(f"### {topic.title.strip()}")
            lines.append("")
            for point in topic.points:
                if point.strip():
                    lines.append(f"- {point.strip()}")
            lines.append("")

    if data.decisions:
        lines.append("## Decisions")
        lines.append("")
        for decision in data.decisions:
            if decision.text.strip():
                lines.append(f"- {decision.text.strip()}")
        lines.append("")

    if data.action_items:
        lines.append("## Action Items")
        lines.append("")
        for item in data.action_items:
            if not item.text.strip():
                continue
            if item.owner:
                lines.append(f"- [ ] {item.owner}: {item.text.strip()}")
            else:
                lines.append(f"- [ ] {item.text.strip()}")
        lines.append("")

    if data.requirements:
        lines.append("## Requirements")
        lines.append("")
        for req in data.requirements:
            if req.text.strip():
                lines.append(f"- {req.text.strip()}")
        lines.append("")

    if data.risks:
        lines.append("## Risks")
        lines.append("")
        for risk in data.risks:
            if risk.text.strip():
                lines.append(f"- {risk.text.strip()}")
        lines.append("")

    if data.open_questions:
        lines.append("## Open Questions")
        lines.append("")
        for question in data.open_questions:
            if question.text.strip():
                lines.append(f"- {question.text.strip()}")
        lines.append("")

    if data.important_dates:
        lines.append("## Important Dates")
        lines.append("")
        for entry in data.important_dates:
            if not entry.text.strip():
                continue
            if entry.date:
                lines.append(f"- **{entry.date}** - {entry.text.strip()}")
            else:
                lines.append(f"- {entry.text.strip()}")
        lines.append("")

    if transcript and transcript.segments:
        lines.append("## Full Transcript")
        lines.append("")
        lines.extend(_render_transcript(transcript))

    text = "\n".join(lines).rstrip() + "\n"
    return text


def _render_transcript(transcript: Transcript) -> list[str]:
    """Group transcript segments by speaker, preserving first-appearance order."""
    order: list[str] = []
    grouped: dict[str, list[str]] = {}
    for seg in transcript.segments:
        if not seg.text.strip():
            continue
        if seg.speaker not in grouped:
            grouped[seg.speaker] = []
            order.append(seg.speaker)
        grouped[seg.speaker].append(seg.text.strip())

    lines: list[str] = []
    for speaker in order:
        lines.append(f"### {speaker}")
        lines.append("")
        for text in grouped[speaker]:
            lines.append(text)
            lines.append("")
    return lines

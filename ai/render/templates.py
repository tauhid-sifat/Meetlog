"""Jinja2-based custom template rendering.

Renders structured meeting data through a user-selectable ``.j2`` template.
Context names exposed to templates: ``data``, ``metadata``, ``transcript``.
Also exposes ``format_date`` and ``format_duration`` helpers (mirroring the
deterministic renderer) so templates stay dependency-light (jinja2 only).
"""

from __future__ import annotations

from datetime import date as _date
from pathlib import Path

from jinja2 import Environment

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


def render_with_template(
    data: StructuredMeetingData,
    metadata: MeetingMetadata,
    transcript: Transcript | None = None,
    template_path: str | Path = "",
) -> str:
    """Render meeting data through the Jinja2 template at ``template_path``."""
    path = Path(str(template_path))
    if not path.is_file():
        raise FileNotFoundError(f"Template not found: {template_path}")
    source = path.read_text(encoding="utf-8")
    env = Environment(autoescape=False, trim_blocks=True, lstrip_blocks=True)
    template = env.from_string(source)
    text = template.render(
        data=data,
        metadata=metadata,
        transcript=transcript,
        format_date=_format_date,
        format_duration=_format_duration,
    )
    return text.rstrip() + "\n"

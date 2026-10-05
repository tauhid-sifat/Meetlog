"""Core data models.

Two layers live here:

* The **raw transcript** (``TranscriptSegment`` / ``Transcript``) which is the
  durable source of truth and must never be destroyed by AI cleanup.
* The **structured meeting data** (``StructuredMeetingData`` and friends) which
  the meeting-intelligence provider returns and the Markdown renderer consumes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


# --------------------------------------------------------------------------- #
# Transcript events (streaming, from the STT provider)
# --------------------------------------------------------------------------- #
@dataclass
class TranscriptEvent:
    """A single streaming event emitted by an STT provider.

    ``kind`` is one of:
      * ``"interim"`` - a low-latency, speculative partial hypothesis
      * ``"segment"`` - a finalized transcript segment
      * ``"error"``   - a provider error (see ``message``)
      * ``"system"``  - a lifecycle notice (see ``message``)
    """

    kind: str
    text: str = ""
    is_final: bool = False
    language: str | None = None
    speaker: str | None = None
    start: float | None = None
    end: float | None = None
    message: str = ""

    @classmethod
    def interim(
        cls,
        text: str,
        *,
        language: str | None = None,
        speaker: str | None = None,
    ) -> "TranscriptEvent":
        return cls(kind="interim", text=text, language=language, speaker=speaker)

    @classmethod
    def segment(
        cls,
        text: str,
        *,
        language: str | None = None,
        speaker: str | None = None,
        start: float | None = None,
        end: float | None = None,
    ) -> "TranscriptEvent":
        return cls(
            kind="segment",
            text=text,
            is_final=True,
            language=language,
            speaker=speaker,
            start=start,
            end=end,
        )

    @classmethod
    def error(cls, message: str) -> "TranscriptEvent":
        return cls(kind="error", message=message)

    @classmethod
    def system(cls, message: str) -> "TranscriptEvent":
        return cls(kind="system", message=message)


# --------------------------------------------------------------------------- #
# Raw transcript (durable)
# --------------------------------------------------------------------------- #
@dataclass
class TranscriptSegment:
    """One finalized transcript segment."""

    id: str
    speaker: str
    start: float
    end: float
    text: str
    language: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TranscriptSegment":
        return cls(
            id=data["id"],
            speaker=data.get("speaker", "Speaker 1"),
            start=float(data.get("start", 0.0)),
            end=float(data.get("end", 0.0)),
            text=data.get("text", ""),
            language=data.get("language", "unknown"),
        )


@dataclass
class Transcript:
    """A full meeting transcript: the durable raw record."""

    meeting_id: str
    segments: list[TranscriptSegment] = field(default_factory=list)
    started_at: str = ""
    ended_at: str | None = None
    provider: str = ""
    model: str = ""

    def add_segment(self, segment: TranscriptSegment) -> None:
        self.segments.append(segment)

    def next_segment_id(self) -> str:
        return f"segment_{len(self.segments) + 1:03d}"

    @property
    def full_text(self) -> str:
        return "\n".join(
            f"[{s.speaker}] {s.text}" for s in self.segments if s.text.strip()
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "provider": self.provider,
            "model": self.model,
            "segments": [s.to_dict() for s in self.segments],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Transcript":
        return cls(
            meeting_id=data.get("meeting_id", ""),
            segments=[
                TranscriptSegment.from_dict(s) for s in data.get("segments", [])
            ],
            started_at=data.get("started_at", ""),
            ended_at=data.get("ended_at"),
            provider=data.get("provider", ""),
            model=data.get("model", ""),
        )


# --------------------------------------------------------------------------- #
# Structured meeting data (AI output)
# --------------------------------------------------------------------------- #
@dataclass
class Decision:
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ActionItem:
    text: str
    owner: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OpenQuestion:
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ImportantDate:
    text: str
    date: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DiscussionTopic:
    title: str
    points: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StructuredMeetingData:
    """The AI's structured understanding of a meeting.

    The AI supplies this data; the application renders it. The model never
    controls the final document formatting.
    """

    title: str = "Meeting"
    summary: str = ""
    decisions: list[Decision] = field(default_factory=list)
    action_items: list[ActionItem] = field(default_factory=list)
    open_questions: list[OpenQuestion] = field(default_factory=list)
    important_dates: list[ImportantDate] = field(default_factory=list)
    discussion_topics: list[DiscussionTopic] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "decisions": [d.to_dict() for d in self.decisions],
            "action_items": [a.to_dict() for a in self.action_items],
            "open_questions": [q.to_dict() for q in self.open_questions],
            "important_dates": [d.to_dict() for d in self.important_dates],
            "discussion_topics": [t.to_dict() for t in self.discussion_topics],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StructuredMeetingData":
        return cls(
            title=data.get("title") or "Meeting",
            summary=data.get("summary") or "",
            decisions=[
                Decision(text=d.get("text", "")) for d in data.get("decisions", [])
            ],
            action_items=[
                ActionItem(text=a.get("text", ""), owner=a.get("owner"))
                for a in data.get("action_items", [])
            ],
            open_questions=[
                OpenQuestion(text=q.get("text", ""))
                for q in data.get("open_questions", [])
            ],
            important_dates=[
                ImportantDate(text=d.get("text", ""), date=d.get("date"))
                for d in data.get("important_dates", [])
            ],
            discussion_topics=[
                DiscussionTopic(
                    title=t.get("title", ""), points=list(t.get("points", []))
                )
                for t in data.get("discussion_topics", [])
            ],
        )


@dataclass
class MeetingMetadata:
    """Metadata persisted next to a meeting's transcript and Markdown."""

    meeting_id: str
    title: str
    date: str
    duration_seconds: float = 0.0
    mode: str = "offline"  # "online" | "offline"
    participants: list[str] = field(default_factory=list)
    provider: str = ""
    model: str = ""
    audio_retained: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MeetingMetadata":
        return cls(**data)

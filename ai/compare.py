"""Meeting comparison (offline, deterministic, no network calls)."""

from __future__ import annotations

from ai.models.transcript import StructuredMeetingData


def _norm(text: str) -> str:
    return (text or "").strip()


def compare_meetings(
    a: StructuredMeetingData,
    b: StructuredMeetingData,
    *,
    label_a: str = "A",
    label_b: str = "B",
) -> dict:
    """Compare two meetings by exact stripped text.

    Action items are compared by ``(owner, text)`` with owner/text stripped
    (``None`` and blank owners both normalize to ``""``).
    """
    del label_a, label_b  # labels only affect rendering, not the diff itself.

    a_dec = {_norm(d.text) for d in a.decisions if _norm(d.text)}
    b_dec = {_norm(d.text) for d in b.decisions if _norm(d.text)}

    def _action_key(item) -> tuple[str, str]:
        owner = (item.owner or "").strip()
        return (owner, _norm(item.text))

    a_act = {_action_key(i) for i in a.action_items if _norm(i.text)}
    b_act = {_action_key(i) for i in b.action_items if _norm(i.text)}

    a_q = {_norm(q.text) for q in a.open_questions if _norm(q.text)}
    b_q = {_norm(q.text) for q in b.open_questions if _norm(q.text)}

    def _fmt_action(key: tuple[str, str]) -> str:
        owner, text = key
        return f"{owner}: {text}" if owner else text

    return {
        "added_decisions": sorted(b_dec - a_dec),
        "removed_decisions": sorted(a_dec - b_dec),
        "added_action_items": sorted(_fmt_action(k) for k in (b_act - a_act)),
        "removed_action_items": sorted(_fmt_action(k) for k in (a_act - b_act)),
        "added_open_questions": sorted(b_q - a_q),
        "removed_open_questions": sorted(a_q - b_q),
    }


def render_comparison(comparison: dict, label_a: str, label_b: str) -> str:
    """Render a comparison dict as deterministic Markdown."""
    lines: list[str] = []
    lines.append("## Meeting Comparison")
    lines.append("")

    new_items: list[str] = []
    for item in comparison.get("added_decisions", []):
        if str(item).strip():
            new_items.append(f"- {str(item).strip()}")
    for item in comparison.get("added_action_items", []):
        if str(item).strip():
            new_items.append(f"- [ ] {str(item).strip()}")
    for item in comparison.get("added_open_questions", []):
        if str(item).strip():
            new_items.append(f"- {str(item).strip()}")

    gone_items: list[str] = []
    for item in comparison.get("removed_decisions", []):
        if str(item).strip():
            gone_items.append(f"- {str(item).strip()}")
    for item in comparison.get("removed_action_items", []):
        if str(item).strip():
            gone_items.append(f"- [ ] {str(item).strip()}")
    for item in comparison.get("removed_open_questions", []):
        if str(item).strip():
            gone_items.append(f"- {str(item).strip()}")

    if new_items:
        lines.append(f"### New since {label_a}")
        lines.append("")
        lines.extend(new_items)
        lines.append("")

    if gone_items:
        lines.append("### No longer present")
        lines.append("")
        lines.extend(gone_items)
        lines.append("")

    _ = label_b  # kept in signature for symmetry with compare_meetings.
    return "\n".join(lines).rstrip() + "\n"

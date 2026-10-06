"""Tests for meeting comparison (offline, deterministic)."""

from __future__ import annotations

from ai.compare import compare_meetings, render_comparison
from ai.models.transcript import (
    ActionItem,
    Decision,
    OpenQuestion,
    StructuredMeetingData,
)


def _action(text: str, owner=None) -> ActionItem:
    return ActionItem(text=text, owner=owner)


def test_added_and_removed_decisions():
    a = StructuredMeetingData(
        title="A", decisions=[Decision(text="Keep"), Decision(text="Drop")]
    )
    b = StructuredMeetingData(
        title="B", decisions=[Decision(text="Keep"), Decision(text="New")]
    )
    result = compare_meetings(a, b)
    assert result["added_decisions"] == ["New"]
    assert result["removed_decisions"] == ["Drop"]


def test_decision_comparison_strips_whitespace():
    a = StructuredMeetingData(title="A", decisions=[Decision(text="  Keep  ")])
    b = StructuredMeetingData(title="B", decisions=[Decision(text="Keep")])
    result = compare_meetings(a, b)
    assert result["added_decisions"] == []
    assert result["removed_decisions"] == []


def test_added_and_removed_action_items():
    a = StructuredMeetingData(
        title="A",
        action_items=[_action("Stay", "Efti"), _action("Gone", "Tauhid")],
    )
    b = StructuredMeetingData(
        title="B",
        action_items=[_action("Stay", "Efti"), _action("Fresh", None)],
    )
    result = compare_meetings(a, b)
    assert result["added_action_items"] == ["Fresh"]
    assert result["removed_action_items"] == ["Tauhid: Gone"]


def test_action_item_comparison_is_owner_aware():
    a = StructuredMeetingData(title="A", action_items=[_action("Deploy", "Efti")])
    b = StructuredMeetingData(title="B", action_items=[_action("Deploy", "Tauhid")])
    result = compare_meetings(a, b)
    assert result["added_action_items"] == ["Tauhid: Deploy"]
    assert result["removed_action_items"] == ["Efti: Deploy"]


def test_action_item_owner_none_vs_blank_is_equal():
    a = StructuredMeetingData(title="A", action_items=[_action("Deploy", None)])
    b = StructuredMeetingData(title="B", action_items=[_action("  Deploy  ", "  ")])
    result = compare_meetings(a, b)
    assert result["added_action_items"] == []
    assert result["removed_action_items"] == []


def test_added_and_removed_open_questions():
    a = StructuredMeetingData(
        title="A",
        open_questions=[OpenQuestion(text="Same?"), OpenQuestion(text="Old?")],
    )
    b = StructuredMeetingData(
        title="B",
        open_questions=[OpenQuestion(text="Same?"), OpenQuestion(text="New?")],
    )
    result = compare_meetings(a, b)
    assert result["added_open_questions"] == ["New?"]
    assert result["removed_open_questions"] == ["Old?"]


def test_empty_comparison_renders_headers_without_items():
    result = compare_meetings(
        StructuredMeetingData(title="A"), StructuredMeetingData(title="B")
    )
    assert result == {
        "added_decisions": [],
        "removed_decisions": [],
        "added_action_items": [],
        "removed_action_items": [],
        "added_open_questions": [],
        "removed_open_questions": [],
    }
    text = render_comparison(result, "A", "B")
    assert "## Meeting Comparison" in text
    assert "### New since" not in text
    assert "### No longer present" not in text


def test_render_comparison_sections_and_labels():
    result = compare_meetings(
        StructuredMeetingData(
            title="A",
            decisions=[Decision(text="Drop")],
            action_items=[_action("Gone", "Tauhid")],
        ),
        StructuredMeetingData(
            title="B",
            decisions=[Decision(text="New")],
            action_items=[_action("Fresh", "Efti")],
        ),
    )
    text = render_comparison(result, "Sprint 1", "Sprint 2")
    assert "## Meeting Comparison" in text
    assert "### New since Sprint 1" in text
    assert "### No longer present" in text
    assert "- New" in text
    assert "- [ ] Efti: Fresh" in text
    assert "- Drop" in text
    assert "- [ ] Tauhid: Gone" in text
    assert text.index("### New since Sprint 1") < text.index("### No longer present")


def test_comparison_is_deterministic():
    a = StructuredMeetingData(
        title="A",
        decisions=[Decision(text="B-dec"), Decision(text="A-dec")],
        action_items=[_action("Z-task"), _action("A-task", "Zed")],
        open_questions=[OpenQuestion(text="Q2"), OpenQuestion(text="Q1")],
    )
    b = StructuredMeetingData(title="B")
    first = compare_meetings(a, b)
    second = compare_meetings(a, b)
    assert first == second
    assert render_comparison(first, "A", "B") == render_comparison(second, "A", "B")

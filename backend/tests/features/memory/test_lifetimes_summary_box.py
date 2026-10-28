"""Lifetimes of facts, the summary's shape and the box's changes (ADR 0071 MM-D3, MM-D4, MM-D9)."""

from datetime import timedelta
from uuid import uuid4

import pytest

from shosai.features.memory.domain.box import BoxReply, NewStatement, plan
from shosai.features.memory.domain.facts import EndReason, FactKind, FactStatus, MemorySource
from shosai.features.memory.domain.lifetimes import (
    candidate_expired,
    erase_after_departure,
    erase_after_meeting_deleted,
    leaves_trace,
    past_chat_retention,
    purgeable,
    refusal_remembered,
)
from shosai.features.memory.domain.summary import (
    SummaryProblem,
    SummaryRefusedError,
    checked,
)
from tests.features.memory.facts_kit import NOW, fact


def test_a_left_workspace_or_a_deleted_meeting_takes_its_facts_a_week_later() -> None:
    assert erase_after_departure(NOW) == NOW + timedelta(days=7)
    assert erase_after_meeting_deleted(NOW) == NOW + timedelta(days=7)


def test_a_team_chats_fact_lives_by_the_chats_retention() -> None:
    assert not past_chat_retention(NOW, 30, NOW + timedelta(days=30))
    assert past_chat_retention(NOW, 30, NOW + timedelta(days=31))
    assert not past_chat_retention(NOW, 365, NOW + timedelta(days=200))
    with pytest.raises(ValueError, match="хранение"):
        past_chat_retention(NOW, 7, NOW)


def test_a_candidate_leaves_after_thirty_days_unless_carried_over() -> None:
    later = NOW + timedelta(days=31)
    assert candidate_expired(fact(status=FactStatus.CANDIDATE), later)
    assert not candidate_expired(fact(status=FactStatus.CANDIDATE), NOW + timedelta(days=29))
    assert not candidate_expired(
        fact(status=FactStatus.CANDIDATE, source=MemorySource.IMPORTED), NOW + timedelta(days=900)
    )
    assert not candidate_expired(fact(), later)


def test_an_ended_fact_goes_after_its_day_and_only_a_refusal_leaves_a_trace() -> None:
    forgotten = fact(status=FactStatus.FORGOTTEN, ended_reason=EndReason.FORGOT, ended_at=NOW)
    declined = fact(status=FactStatus.FORGOTTEN, ended_reason=EndReason.TURNED_DOWN, ended_at=NOW)
    faded = fact(status=FactStatus.FORGOTTEN, ended_reason=EndReason.EXPIRED, ended_at=NOW)
    superseded = fact(valid_to=NOW, superseded_by=uuid4())
    for ended in (forgotten, declined, faded, superseded):
        assert not purgeable(ended, NOW + timedelta(hours=24))
        assert purgeable(ended, NOW + timedelta(hours=25))
    assert not purgeable(fact(), NOW + timedelta(days=9_000))
    assert [leaves_trace(ended) for ended in (forgotten, declined, faded, superseded)] == [
        True, True, False, False,
    ]  # fmt: skip
    assert refusal_remembered(NOW, NOW + timedelta(days=90))
    assert not refusal_remembered(NOW, NOW + timedelta(days=91))


def test_a_summary_in_shape_is_kept() -> None:
    summary = checked([("Work", "Leads product at Lumen.")], ["What do you know about my team?"])
    assert summary.sections[0].title == "Work"
    assert summary.suggestions == ("What do you know about my team?",)


@pytest.mark.parametrize(
    ("sections", "suggestions", "problem"),
    [
        ([], [], SummaryProblem.NO_SECTIONS),
        ([("A", "b")] * 6, [], SummaryProblem.TOO_MANY),
        ([("A", "b")], ["q"] * 4, SummaryProblem.TOO_MANY),
        ([(" ", "b")], [], SummaryProblem.EMPTY),
        ([("A", "b" * 1_201)], [], SummaryProblem.TOO_LONG),
        ([("A", "Leads **product**.")], [], SummaryProblem.MARKUP),
        ([("A", "- a list")], [], SummaryProblem.MARKUP),
        ([("A", "## Heading")], [], SummaryProblem.MARKUP),
        ([("A", "Uses `code`.")], [], SummaryProblem.MARKUP),
        ([("A", "b"), ("a", "c")], [], SummaryProblem.REPEATED),
    ],
)
def test_a_summary_out_of_shape_is_refused(
    sections: list[tuple[str, str]], suggestions: list[str], problem: SummaryProblem
) -> None:
    with pytest.raises(SummaryRefusedError) as refused:
        checked(sections, suggestions)
    assert refused.value.problem is problem


def test_the_box_changes_only_the_facts_it_was_shown() -> None:
    first, second, third = uuid4(), uuid4(), uuid4()
    refs = {"F1": first, "F2": second, "F3": third}
    reply = BoxReply(
        answer="  You lead product at Lumen. ",
        remember=[
            NewStatement("Lives in Berlin", FactKind.FACT),
            NewStatement("Lives in Berlin", FactKind.FACT),
            NewStatement("   ", FactKind.FACT),
        ],
        update=[("F1", "Leads design"), ("F9", "made up"), ("F2", "Old"), ("F1", "Twice")],
        forget=["F2", "F2", "F8"],
    )
    result = plan(reply, refs)
    assert result.answer == "You lead product at Lumen."
    assert result.remember == (NewStatement("Lives in Berlin", FactKind.FACT),)
    assert [(item.fact_id, item.statement) for item in result.update] == [(first, "Leads design")]
    assert result.forget == (second,)
    assert result.changes == 3


def test_a_box_reply_without_a_question_has_no_answer() -> None:
    result = plan(BoxReply(answer="   ", remember=[], update=[], forget=[]), {})
    assert result.answer is None
    assert result.changes == 0

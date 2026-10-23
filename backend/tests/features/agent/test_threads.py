"""Threads, questions and the erasure of a departed workspace's threads (AG-D2, AG-D3)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.agent.domain.threads import (
    ELLIPSIS,
    TITLE_MAX,
    Erasure,
    ScopeKind,
    ThreadRule,
    ThreadRuleError,
    ThreadScope,
    TurnKind,
    check_question,
    check_replacement,
    clean_title,
    erase_after,
    erasure,
    title_from_question,
)

NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)


def rule_of(error: pytest.ExceptionInfo[ThreadRuleError]) -> ThreadRule:
    return error.value.rule


def test_a_scope_names_exactly_the_space_of_its_kind() -> None:
    org, hub = uuid.uuid4(), uuid.uuid4()

    assert ThreadScope.personal().kind is ScopeKind.PERSONAL
    assert ThreadScope(ScopeKind.WORKSPACE, org_id=org).org_id == org
    assert ThreadScope(ScopeKind.HUB, hub_id=hub).hub_id == hub
    for kind, org_id, hub_id in (
        (ScopeKind.PERSONAL, org, None),
        (ScopeKind.WORKSPACE, None, None),
        (ScopeKind.WORKSPACE, org, hub),
        (ScopeKind.HUB, org, None),
    ):
        with pytest.raises(ThreadRuleError) as raised:
            ThreadScope(kind, org_id=org_id, hub_id=hub_id)
        assert rule_of(raised) is ThreadRule.SCOPE_INVALID


def test_a_title_is_trimmed_and_bounded() -> None:
    assert clean_title("  Budget \n review ") == "Budget review"
    for wrong in ("   ", "x" * (TITLE_MAX + 1)):
        with pytest.raises(ThreadRuleError) as raised:
            clean_title(wrong)
        assert rule_of(raised) is ThreadRule.TITLE_INVALID


@given(st.text(max_size=600))
def test_a_question_always_gives_a_title_within_the_bound(question: str) -> None:
    title = title_from_question(question)

    assert 0 < len(title) <= TITLE_MAX
    assert "\n" not in title


def test_a_long_first_line_is_cut_at_a_word() -> None:
    title = title_from_question("word " * 60 + "\nsecond line")

    assert title.endswith(ELLIPSIS)
    assert not title.removesuffix(ELLIPSIS).endswith(" ")
    assert len(title) <= TITLE_MAX


def test_a_question_is_text_or_an_attachment_and_at_most_five_files() -> None:
    assert check_question("  Hello ", 0) == "Hello"
    assert not check_question("", 1)
    for text, files, rule in (
        ("", 0, ThreadRule.QUESTION_INVALID),
        ("x" * 4_001, 0, ThreadRule.QUESTION_INVALID),
        ("Hello", 6, ThreadRule.TOO_MANY_ATTACHMENTS),
    ):
        with pytest.raises(ThreadRuleError) as raised:
            check_question(text, files)
        assert rule_of(raised) is rule


def test_regenerate_and_edit_name_the_last_question_only() -> None:
    last, older = uuid.uuid4(), uuid.uuid4()

    check_replacement(TurnKind.NEW, None, last)
    check_replacement(TurnKind.REGENERATE, last, last)
    check_replacement(TurnKind.EDIT, last, last)
    for kind, named in (
        (TurnKind.NEW, last),
        (TurnKind.REGENERATE, older),
        (TurnKind.EDIT, None),
    ):
        with pytest.raises(ThreadRuleError) as raised:
            check_replacement(kind, named, last)
        assert rule_of(raised) is ThreadRule.NOT_LAST_QUESTION


@given(minutes=st.integers(min_value=0, max_value=14 * 24 * 60), member_again=st.booleans())
def test_a_departed_workspace_s_thread_waits_seven_days_unless_access_returns(
    *, minutes: int, member_again: bool
) -> None:
    due = erase_after(NOW)
    verdict = erasure(due, NOW + timedelta(minutes=minutes), member_again=member_again)

    if member_again:
        assert verdict is Erasure.RESTORED
    elif minutes >= 7 * 24 * 60:
        assert verdict is Erasure.ERASE
    else:
        assert verdict is Erasure.WAIT

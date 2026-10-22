"""How a Jira issue and a task map onto each other (TK-D8, draft lessons of `features/jira`)."""

from datetime import date

from hypothesis import given
from hypothesis import strategies as st
from pydantic import JsonValue

from shosai.features.tasks.domain.jira import (
    PRIORITY_OF_ID,
    UNMAPPED,
    StatusCategory,
    category_of,
    document_of_text,
    due_of,
    jira_priority_id,
    priority_after_pull,
    priority_of,
    status_of,
    text_of_document,
    title_of,
)
from shosai.features.tasks.domain.tasks import TITLE_MAX, Priority, TaskStatus

priorities = st.none() | st.sampled_from(list(Priority))


@given(st.text(max_size=20) | st.sampled_from([category.value for category in StatusCategory]))
def test_only_the_done_category_is_done(key: str) -> None:
    assert (status_of(key) is TaskStatus.DONE) == (key == "done")


def test_every_status_goes_out_in_its_own_category() -> None:
    for status in TaskStatus:
        assert status_of(category_of(status).value) is status
    assert status_of(StatusCategory.UNDEFINED.value) is TaskStatus.TODO


@given(st.text(max_size=8).filter(lambda raw: raw not in PRIORITY_OF_ID), priorities)
def test_an_unmapped_priority_never_changes_the_task(
    priority_id: str, current: Priority | None
) -> None:
    assert priority_of(priority_id) is UNMAPPED
    assert priority_after_pull(current, priority_id) is current


@given(priorities)
def test_only_a_priority_of_the_default_scheme_is_ever_written(priority: Priority | None) -> None:
    written = jira_priority_id(priority)

    if priority is None:
        assert written is None
    else:
        assert written in PRIORITY_OF_ID
        assert priority_of(written) is priority


def test_no_priority_in_jira_clears_it() -> None:
    assert priority_after_pull(Priority.HIGH, None) is None
    assert priority_after_pull(None, "1") is Priority.HIGH
    assert priority_after_pull(None, "5") is Priority.LOW


def test_a_due_date_is_a_calendar_day() -> None:
    assert due_of("2026-10-24") == date(2026, 10, 24)
    assert due_of(None) is None
    assert due_of("24.10.2026") is None


def test_a_summary_becomes_a_title_within_bounds() -> None:
    assert title_of("  Fix\tthe   login ") == "Fix the login"
    assert len(title_of("я " * 300)) <= TITLE_MAX


def test_a_document_reads_as_plain_text_with_lists_marked() -> None:
    document: dict[str, JsonValue] = {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "heading", "content": [{"type": "text", "text": "План"}]},
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Спросить "},
                    {"type": "mention", "attrs": {"id": "1", "text": "@Анна"}},
                    {"type": "hardBreak"},
                    {"type": "text", "text": "до пятницы"},
                ],
            },
            {
                "type": "orderedList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "один"}]}
                        ],
                    },
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "два"}]}
                        ],
                    },
                ],
            },
            {"type": [1], "content": "not a list"},
        ],
    }

    assert text_of_document(document) == "План\nСпросить @Анна\nдо пятницы\n1. один\n2. два"
    assert text_of_document(None) == ""


def test_a_document_nested_past_its_depth_loses_only_the_deep_part() -> None:
    node: dict[str, JsonValue] = {
        "type": "paragraph",
        "content": [{"type": "text", "text": "глубоко"}],
    }
    for _ in range(100):
        node = {"type": "blockquote", "content": [node]}

    assert text_of_document({"type": "doc", "content": [node]}) == ""


@given(
    st.lists(
        st.text(alphabet=st.characters(blacklist_categories=("Cs", "Cc", "Zl", "Zp")), min_size=1)
        .map(str.strip)
        .filter(bool),
        max_size=5,
    )
)
def test_text_goes_out_as_paragraphs_and_reads_back(lines: list[str]) -> None:
    text = "\n".join(lines)

    assert (
        text_of_document(document_of_text(text))
        == "\n".join(line.rstrip() for line in lines).strip()
    )

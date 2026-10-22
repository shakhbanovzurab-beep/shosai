"""A meeting's action items as tasks and the freeze rule (TK-D3)."""

import uuid
from datetime import date

from hypothesis import given
from hypothesis import strategies as st

from shosai.features.tasks.domain.action_items import (
    ActionItem,
    MeetingSpace,
    ProjectedTask,
    Projection,
    TaskSetState,
    projected_tasks,
    projection_for,
)
from shosai.features.tasks.domain.members import MemberName, match_member, name_key
from shosai.features.tasks.domain.tasks import TITLE_MAX, Assignee

OWNER = uuid.uuid4()


def item(text: str, owner: str | None = None, *, own: bool = False) -> ActionItem:
    return ActionItem(uuid.uuid4(), text, owner, own, date(2026, 10, 24))


revisions = st.lists(
    st.lists(st.sampled_from(["Отправить договор", "Send the deck", "議事録を送る"]), max_size=4),
    min_size=1,
    max_size=5,
)


@given(revisions, st.data())
def test_a_touched_set_never_changes_and_an_untouched_one_follows_the_latest_revision(
    texts: list[list[str]], data: st.DataObject
) -> None:
    by_revision = {
        number: tuple(item(text) for text in items) for number, items in enumerate(texts, 1)
    }
    # Ревизии приходят в любом порядке и повторно; касания человека — между ними.
    events = data.draw(
        st.lists(st.sampled_from([*by_revision, 0]), min_size=1, max_size=12), label="events"
    )
    state: TaskSetState | None = None
    tasks: tuple[ProjectedTask, ...] = ()
    frozen: tuple[ProjectedTask, ...] | None = None
    latest = 0
    for event in events:
        if event == 0:
            if state is not None and frozen is None:
                state = TaskSetState(state.revision, touched=True)
                frozen = tasks
            continue
        latest = max(latest, event)
        if projection_for(state, event, kept=True) is Projection.APPLIED:
            tasks = projected_tasks(by_revision[event], MeetingSpace(OWNER))
            state = TaskSetState(event, touched=False)

    if frozen is not None:
        assert tasks == frozen
    elif latest:
        assert tasks == projected_tasks(by_revision[latest], MeetingSpace(OWNER))


def test_what_a_revision_does_to_a_set() -> None:
    assert projection_for(None, 1, kept=False) is Projection.NOT_KEPT
    assert projection_for(None, 1, kept=True) is Projection.APPLIED
    assert projection_for(TaskSetState(2, touched=False), 2, kept=True) is Projection.SKIPPED_SEEN
    assert projection_for(TaskSetState(2, touched=False), 1, kept=True) is Projection.SKIPPED_SEEN
    assert projection_for(TaskSetState(1, touched=True), 2, kept=True) is Projection.SKIPPED_TOUCHED
    assert projection_for(TaskSetState(1, touched=False), 2, kept=True) is Projection.APPLIED


def test_a_long_action_item_gets_a_short_title_and_keeps_its_text() -> None:
    text = "слово " * 90
    task = projected_tasks([item(text)], MeetingSpace(OWNER))[0]

    assert len(task.title) <= TITLE_MAX
    assert task.title.endswith("…")
    assert not task.title.endswith(" …")
    assert task.description == text.strip()
    short = projected_tasks([item("Позвонить Ивану")], MeetingSpace(OWNER))[0]
    assert (short.title, short.description, short.due_on) == (
        "Позвонить Ивану",
        "",
        date(2026, 10, 24),
    )


def test_an_item_without_text_makes_no_task() -> None:
    assert projected_tasks([item("   ")], MeetingSpace(OWNER)) == ()


def test_who_does_a_personal_meetings_task() -> None:
    tasks = projected_tasks(
        [item("A", own=True), item("B", " Анна "), item("C"), item("D", "x" * 120)],
        MeetingSpace(OWNER),
    )

    assert [task.assignee for task in tasks] == [
        Assignee(),
        Assignee(name="Анна"),
        Assignee(),
        Assignee(name="x" * 80),
    ]


def test_who_does_a_workspace_meetings_task() -> None:
    org, anna, ivan = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    members = (
        MemberName(anna, "Анна Смирнова"),
        MemberName(ivan, "Иван"),
        MemberName(uuid.uuid4(), "Иван"),
    )
    space = MeetingSpace(OWNER, org, members)
    tasks = projected_tasks(
        [item("A", own=True), item("B", "анна  смирнова"), item("C", "Иван"), item("D", "Пётр")],
        space,
    )

    assert [task.assignee for task in tasks] == [
        Assignee(user_id=OWNER),
        Assignee(user_id=anna),
        Assignee(name="Иван"),
        Assignee(name="Пётр"),
    ]


def test_a_name_matches_without_case_width_or_spacing_differences() -> None:
    member = uuid.uuid4()

    assert name_key("  ＡＮＮＡ   Lee ") == "anna lee"
    assert match_member("anna lee", [MemberName(member, "ＡＮＮＡ Lee")]) == member
    assert match_member("Straße", [MemberName(member, "STRASSE")]) == member
    assert match_member(" ", [MemberName(member, " ")]) is None
    assert match_member("Анна", []) is None

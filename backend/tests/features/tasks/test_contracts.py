"""Tasks' public surface follows core's rules (tasks plan §3.2, TK-D10)."""

import inspect
import uuid

from shosai.composition.features import FEATURES
from shosai.core.events.domain_event import DomainEvent
from shosai.core.ports.keys import PortKey
from shosai.features.tasks import contracts
from shosai.features.tasks.contracts import BoardNotFoundError, TaskNotFoundError, events
from shosai.features.tasks.contracts.events import TaskCompleted
from shosai.features.tasks.domain.tasks import TaskSource
from shosai.features.tasks.module import TASKS


def test_every_published_event_is_registered_and_named_for_the_slice() -> None:
    declared = {
        value
        for value in vars(events).values()
        if inspect.isclass(value) and issubclass(value, DomainEvent) and value is not DomainEvent
    }

    assert set(TASKS.events) == declared
    assert {event.event_type for event in TASKS.events} == {
        "tasks.task.assigned",
        "tasks.task.due_changed",
        "tasks.task.completed",
        "tasks.task.reopened",
        "tasks.task.deleted",
    }
    assert TASKS in FEATURES


def test_the_ports_are_named_for_the_slice() -> None:
    keys = {value.name for value in vars(contracts).values() if isinstance(value, PortKey)}

    assert keys == {
        "tasks.meeting_tasks",
        "tasks.task_reader",
        "tasks.task_intake",
        "tasks.board_reader",
    }


def test_a_missing_task_or_board_is_a_404_with_its_code() -> None:
    assert (TaskNotFoundError().code, int(TaskNotFoundError().status)) == ("task_not_found", 404)
    assert (BoardNotFoundError().code, int(BoardNotFoundError().status)) == ("board_not_found", 404)


def test_an_event_names_its_task_and_people_by_id_only() -> None:
    event = TaskCompleted(task_id=uuid.uuid4(), user_id=uuid.uuid4(), source=TaskSource.MEETING)

    assert event.org_id is None
    assert event.model_dump(mode="json")["source"] == "meeting"

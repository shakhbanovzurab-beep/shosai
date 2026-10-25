"""What Leo's change of a task sends, and how its card shows it (tasks plan; agent step 9b).

The plan keeps only the fields the model sent; the change and the edit are made from them at
approval. The card shows each sent field's new value, the word for none for a cleared one,
and whether the details changed or went — never the details' text.
"""

from datetime import date
from typing import Final
from uuid import UUID

from pydantic import JsonValue

from shosai.core.agent_tools.results import PreviewParam
from shosai.features.tasks.application.task_edits import Edit
from shosai.features.tasks.channels.agent_previews import CLEARED
from shosai.features.tasks.channels.agent_write_tools import TaskChanged, UpdateTask
from shosai.features.tasks.domain.changes import UNSET, TaskChange, Unset
from shosai.features.tasks.domain.tasks import Assignee, Priority, TaskStatus
from shosai.features.tasks.infrastructure.task_records import TaskRecord

FIELDS: Final = ("title", "description", "due_on", "starts_on", "priority", "assignee_id",
                 "assignee_name")  # fmt: skip


def change_of(sent: dict[str, JsonValue]) -> tuple[TaskChange, Edit]:
    """The change and the edit a plan's fields make; absent fields stay."""

    def day(name: str) -> date | None:
        raw = sent[name]
        return None if raw is None else date.fromisoformat(str(raw))

    assignee: Assignee | Unset = UNSET
    if "assignee_id" in sent:
        raw = sent["assignee_id"]
        assignee = Assignee(user_id=None if raw is None else UUID(str(raw)))
    elif "assignee_name" in sent:
        raw = sent["assignee_name"]
        assignee = Assignee(name=None if raw is None else str(raw))
    priority = sent.get("priority")
    change = TaskChange(
        title=str(sent["title"]) if "title" in sent else UNSET,
        description=str(sent["description"]) if "description" in sent else UNSET,
        due_on=day("due_on") if "due_on" in sent else UNSET,
        starts_on=day("starts_on") if "starts_on" in sent else UNSET,
        priority=(None if priority is None else Priority(str(priority)))
        if "priority" in sent else UNSET,
        assignee=assignee,
    )  # fmt: skip
    edit = Edit(
        change=change, sent_assignee_id="assignee_id" in sent,
        sent_assignee_name="assignee_name" in sent,
    )  # fmt: skip
    return change, edit


def sent_of(args: UpdateTask) -> dict[str, JsonValue]:
    """The fields the model sent, as the plan keeps them."""
    dumped = args.model_dump(mode="json")
    return {name: dumped[name] for name in FIELDS if name in args.model_fields_set}


def changed(record: TaskRecord) -> TaskChanged:
    """The task as a change leaves it."""
    priority = None if record.priority is None else Priority(record.priority)
    return TaskChanged(
        task_id=record.id, title=record.title, status=TaskStatus(record.status),
        due_on=record.due_on, priority=priority,
    )  # fmt: skip


def update_params(
    title: str | None, sent: dict[str, JsonValue], assignee: str | None
) -> dict[str, PreviewParam]:
    """The card of a change: the task's title, then each sent field as it becomes."""

    def becomes(name: str) -> PreviewParam:
        if name not in sent:
            return None
        raw = sent[name]
        return CLEARED if raw is None else str(raw)

    details = None
    if "description" in sent:
        details = "changed" if sent["description"] else CLEARED
    return {
        "title": title, "new_title": becomes("title"), "due_on": becomes("due_on"),
        "starts_on": becomes("starts_on"), "priority": becomes("priority"),
        "assignee": assignee, "details": details,
    }  # fmt: skip

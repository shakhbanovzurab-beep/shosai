"""What other slices may use of tasks (tasks plan §3.2).

Tasks is the one store of a person's work (SM-3). Notes shows a meeting's action items as
its tasks and ticks them from the shipped desktop clients through `MeetingTasks`;
proactive, hubs and Leo read tasks through `TaskReader`; hubs and mail hand work over
through `TaskIntake`, and hubs picks the board its work goes to through `BoardReader`.
Every read runs inside workspaces' access policy, so a task the viewer may not read is
absent (inv-14). The events are in `contracts.events`.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from http import HTTPStatus
from typing import Final, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.errors import AppError
from shosai.core.ports.keys import PortKey
from shosai.features.tasks.domain.tasks import Assignee, Priority, TaskSource, TaskStatus
from shosai.features.workspaces.contracts import Viewer

__all__ = [
    "BOARD_READER",
    "MEETING_TASKS",
    "TASK_INTAKE",
    "TASK_READER",
    "Assignee",
    "BoardFacts",
    "BoardNotFoundError",
    "BoardReader",
    "Handover",
    "MeetingTask",
    "MeetingTasks",
    "Priority",
    "TaskDraft",
    "TaskFacts",
    "TaskIntake",
    "TaskNotFoundError",
    "TaskReader",
    "TaskSource",
    "TaskStatus",
]


class TaskNotFoundError(AppError):
    """No such task the caller may use: missing, or not readable by them (404)."""

    def __init__(self) -> None:
        super().__init__("task_not_found", HTTPStatus.NOT_FOUND)


class BoardNotFoundError(AppError):
    """No such board of the person (404)."""

    def __init__(self) -> None:
        super().__init__("board_not_found", HTTPStatus.NOT_FOUND)


@dataclass(frozen=True, slots=True)
class MeetingTask:
    """A task made from one of a meeting's action items, keyed by the item's finding."""

    task_id: UUID
    finding_id: UUID
    title: str
    status: TaskStatus
    due_on: date | None
    assignee: Assignee


class MeetingTasks(Protocol):
    """A meeting's action items as tasks (TK-D3): for its page and the native note."""

    async def of(
        self, session: AsyncSession, viewer: Viewer, meeting_id: UUID
    ) -> Sequence[MeetingTask]:
        """The meeting's tasks the viewer may read, in the order of its notes."""
        ...

    async def set_done(
        self,
        session: AsyncSession,
        viewer: Viewer,
        meeting_id: UUID,
        finding_id: UUID,
        *,
        done: bool,
    ) -> None:
        """Tick or untick the task of this action item; `TaskNotFoundError` if there is none.

        A tick by a person touches the meeting's set, so later revisions of its notes leave
        its tasks as they are; a repeated tick changes nothing.
        """
        ...


@dataclass(frozen=True, slots=True)
class TaskFacts:
    """A task the viewer may read, as other slices see it."""

    task_id: UUID
    user_id: UUID
    org_id: UUID | None
    title: str
    status: TaskStatus
    priority: Priority | None
    due_on: date | None
    assignee: Assignee
    source: TaskSource
    source_meeting_id: UUID | None


class TaskReader(Protocol):
    """Tasks a viewer may read, through workspaces' access policy (inv-14)."""

    async def facts(
        self, session: AsyncSession, viewer: Viewer, task_ids: Collection[UUID]
    ) -> Mapping[UUID, TaskFacts]:
        """The readable ones among `task_ids`; the others are absent."""
        ...


@dataclass(frozen=True, slots=True)
class TaskDraft:
    """A task another slice hands over: its words, day and who does it."""

    title: str
    description: str = ""
    priority: Priority | None = None
    due_on: date | None = None
    assignee: Assignee = field(default_factory=Assignee)


@dataclass(frozen=True, slots=True)
class Handover:
    """Whose tasks another slice creates, where from, and on which of the owner's boards."""

    owner_id: UUID
    org_id: UUID | None
    source: TaskSource
    board_id: UUID | None = None


class TaskIntake(Protocol):
    """Work another slice hands over as tasks: a hub's agreed work, a mail's follow-up."""

    async def create(
        self, session: AsyncSession, handover: Handover, drafts: Sequence[TaskDraft]
    ) -> tuple[UUID, ...]:
        """Create the tasks in the transaction's space, at the top of the board if one is named.

        A board that is not the owner's is `BoardNotFoundError`; a draft breaking a task's
        rules creates none of them.
        """
        ...


@dataclass(frozen=True, slots=True)
class BoardFacts:
    """A board of the person, for a picker."""

    board_id: UUID
    name: str
    synced_with_jira: bool


class BoardReader(Protocol):
    """The person's boards, read in the caller's transaction."""

    async def boards(self, session: AsyncSession, user_id: UUID) -> Sequence[BoardFacts]:
        """The person's boards, oldest first."""
        ...

    async def exists(self, session: AsyncSession, user_id: UUID, board_id: UUID) -> bool:
        """Whether the board is the person's."""
        ...


MEETING_TASKS: Final = PortKey[MeetingTasks]("tasks.meeting_tasks")
TASK_READER: Final = PortKey[TaskReader]("tasks.task_reader")
TASK_INTAKE: Final = PortKey[TaskIntake]("tasks.task_intake")
BOARD_READER: Final = PortKey[BoardReader]("tasks.board_reader")

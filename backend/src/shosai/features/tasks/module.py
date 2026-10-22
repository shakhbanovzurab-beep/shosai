"""The tasks slice as composition sees it (tasks plan §3.1).

Step 1 published the contract, the events and the domain; step 2 added the tables in each
home, the shareable `task` with its parent and named-reader rules (TK-D2), and the handler
of a person's data; step 3a the one task API (`/v1/tasks*`) and the task reader. Boards,
the action items from meetings, Leo's tools and Jira join in the later steps.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.features.tasks.application.account_data import ACCOUNT_DATA, TasksAccountData
from shosai.features.tasks.application.task_edits import TaskEdits
from shosai.features.tasks.application.task_reads import TaskReads
from shosai.features.tasks.application.task_writes import TaskWrites
from shosai.features.tasks.channels.http.tasks import build_tasks_router
from shosai.features.tasks.contracts import TASK_READER
from shosai.features.tasks.contracts.events import (
    TaskAssigned,
    TaskCompleted,
    TaskDeleted,
    TaskDueChanged,
    TaskReopened,
)
from shosai.features.tasks.infrastructure.board_records import (
    BoardColumnRecord,
    BoardRecord,
    TaskPlacementRecord,
    TaskSettingsRecord,
)
from shosai.features.tasks.infrastructure.task_records import (
    TASK_RESOURCE,
    MeetingTaskSetRecord,
    TaskRecord,
)


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """Bind the routes of tasks, the task reader and the handler of a person's data."""
    transactions, ports = services.transactions, services.ports
    reads = TaskReads(transactions, ports)
    writes = TaskWrites(transactions, ports, (services.outbox, services.effects))
    edits = TaskEdits(transactions, ports, services.outbox)
    yield FeatureParts(
        http_routers=(build_tasks_router((reads, writes, edits), ports),),
        provides=(
            ACCOUNT_DATA_HANDLERS.bind(TasksAccountData(transactions)),
            TASK_READER.bind(reads),
        ),
    )


TASKS = FeatureModule(
    name="tasks",
    build=build,
    models=(
        TaskRecord,
        MeetingTaskSetRecord,
        BoardRecord,
        BoardColumnRecord,
        TaskPlacementRecord,
        TaskSettingsRecord,
    ),
    events=(TaskAssigned, TaskDueChanged, TaskCompleted, TaskReopened, TaskDeleted),
    account_data=(ACCOUNT_DATA,),
    shareable=(TASK_RESOURCE,),
)

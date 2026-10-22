"""The tasks slice as composition sees it (tasks plan §3.1).

Step 1 published the contract, the events and the domain; step 2 adds the tables in each
home, the shareable `task` with its parent and named-reader rules (TK-D2), and the handler
of a person's data. The routes, the action items from meetings, Leo's tools and Jira join
in the later steps.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.features.tasks.application.account_data import ACCOUNT_DATA, TasksAccountData
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
    """Bind the handler of a person's data."""
    yield FeatureParts(
        provides=(ACCOUNT_DATA_HANDLERS.bind(TasksAccountData(services.transactions)),),
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

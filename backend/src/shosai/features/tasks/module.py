"""The tasks slice as composition sees it (tasks plan §3.1).

Step 1 publishes the contract, the events and the domain; tables, the access rules, the
routes, the action items from meetings, Leo's tools and Jira join in the later steps.
"""

from shosai.core.features import FeatureModule
from shosai.features.tasks.contracts.events import (
    TaskAssigned,
    TaskCompleted,
    TaskDeleted,
    TaskDueChanged,
    TaskReopened,
)

TASKS = FeatureModule(
    name="tasks",
    events=(TaskAssigned, TaskDueChanged, TaskCompleted, TaskReopened, TaskDeleted),
)

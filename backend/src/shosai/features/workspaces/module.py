"""The workspaces slice as composition sees it (workspaces plan §3.1).

Step 1 publishes the contract: the events other slices may subscribe to. Tables, the
access policy, the services and the routes join in the later steps of the plan.
"""

from shosai.core.features import FeatureModule
from shosai.features.workspaces.contracts.events import (
    AccessChanged,
    KnowledgeItemAdded,
    KnowledgeItemRemoved,
    MeetingShared,
    MeetingUnshared,
    MemberJoined,
    MemberRemoved,
    MemberRoleChanged,
    ProjectDeleted,
    TeamDeleted,
    WorkspaceCreated,
    WorkspaceDeleted,
    WorkspaceDeletionCancelled,
    WorkspaceDeletionScheduled,
    WorkspaceResumed,
    WorkspaceSuspended,
)

WORKSPACES = FeatureModule(
    name="workspaces",
    events=(
        WorkspaceCreated,
        WorkspaceSuspended,
        WorkspaceResumed,
        WorkspaceDeletionScheduled,
        WorkspaceDeletionCancelled,
        WorkspaceDeleted,
        MemberJoined,
        MemberRemoved,
        MemberRoleChanged,
        TeamDeleted,
        ProjectDeleted,
        AccessChanged,
        MeetingShared,
        MeetingUnshared,
        KnowledgeItemAdded,
        KnowledgeItemRemoved,
    ),
)

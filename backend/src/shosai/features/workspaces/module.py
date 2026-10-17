"""The workspaces slice as composition sees it (workspaces plan §3.1).

Built in every role: the API binds the ports other slices call, the workers run the
account window's task and its consumers. The routes join in the later steps of the plan.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.account_data.spec import AccountDataSpec, TableCoverage, Treatment
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.features.workspaces.application.access_policy import WorkspaceAccessPolicy
from shosai.features.workspaces.application.account_data import OWNER, WorkspacesAccountData
from shosai.features.workspaces.channels.consumers import AccountWindow
from shosai.features.workspaces.channels.tasks import task_handlers
from shosai.features.workspaces.contracts import ACCESS_POLICY, AUDIT_LOG, MEMBERSHIP_READER
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
from shosai.features.workspaces.infrastructure.access_records import (
    Invitation,
    ResourceGrant,
    WorkspaceKnowledgeItem,
    WorkspaceMeetingShare,
)
from shosai.features.workspaces.infrastructure.audit_log import WorkspaceAuditLog
from shosai.features.workspaces.infrastructure.audit_records import DirectoryDomain, OrgAuditEvent
from shosai.features.workspaces.infrastructure.membership_reader import MembershipDirectory
from shosai.features.workspaces.infrastructure.organization_records import (
    Membership,
    Organization,
    Project,
    Team,
    TeamMember,
)

# Членства человека: стираются как удаление из пространства, строка остаётся без должности.
ACCOUNT_DATA = AccountDataSpec(OWNER, (TableCoverage("memberships", Treatment.ERASE),))


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """Bind the ports and the registry's handler; register the account window's task."""
    audit = WorkspaceAuditLog()
    account_data = WorkspacesAccountData(services.transactions, services.outbox, audit)
    yield FeatureParts(
        task_handlers=task_handlers(services.transactions),
        subscriptions=AccountWindow(services.tasks).subscriptions(),
        provides=(
            ACCESS_POLICY.bind(WorkspaceAccessPolicy(services.outbox, audit)),
            MEMBERSHIP_READER.bind(MembershipDirectory()),
            AUDIT_LOG.bind(audit),
            ACCOUNT_DATA_HANDLERS.bind(account_data),
        ),
    )


WORKSPACES = FeatureModule(
    name="workspaces",
    build=build,
    account_data=(ACCOUNT_DATA,),
    models=(
        Organization,
        Membership,
        Team,
        TeamMember,
        Project,
        Invitation,
        ResourceGrant,
        WorkspaceMeetingShare,
        WorkspaceKnowledgeItem,
        OrgAuditEvent,
        DirectoryDomain,
    ),
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

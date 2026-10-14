"""Identity's own event consumers: the directory and the operators' audit log (EU).

The account changes in its home; the directory in the EU learns of it from the event, in
an EU transaction with its delivery mark, since no transaction spans two homes. The
erasure itself frees the address directly, as a step of the saga. An operator's action
reaches the EU audit log the same way (SM-12).
"""

from datetime import timedelta
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.subscriptions import EventSubscription, ReceivedEvent
from shosai.core.kernel.homes import Home
from shosai.core.tasks.queues import TaskQueue
from shosai.features.identity.application.account_states import AUDITED
from shosai.features.identity.contracts import (
    AccountDeletionCancelled,
    AccountDeletionScheduled,
    OperatorActed,
)
from shosai.features.identity.domain.account_actions import DIRECTORY_CHANGES
from shosai.features.identity.domain.registration import DirectoryState
from shosai.features.identity.infrastructure.directory import follow_account
from shosai.features.identity.infrastructure.operator_audit import record_action

DEADLINE: Final = timedelta(seconds=30)
# Какое действие над аккаунтом стоит за записью аудита; у смены ролей — никакого.
ACCOUNT_ACTIONS: Final = {audit: action for action, audit in AUDITED.items()}


async def hide_in_directory(
    session: AsyncSession, received: ReceivedEvent[AccountDeletionScheduled]
) -> None:
    """The address stays taken, its row marked as scheduled for deletion."""
    change = (frozenset({DirectoryState.ACTIVE}), DirectoryState.DELETION_SCHEDULED)
    await follow_account(session, received.event.user_id, change, received.occurred_at)


async def show_in_directory(
    session: AsyncSession, received: ReceivedEvent[AccountDeletionCancelled]
) -> None:
    """A sign-in cancelled the deletion: the row is active again."""
    change = (frozenset({DirectoryState.DELETION_SCHEDULED}), DirectoryState.ACTIVE)
    await follow_account(session, received.event.user_id, change, received.occurred_at)


async def audit_operator_action(
    session: AsyncSession, received: ReceivedEvent[OperatorActed]
) -> None:
    """One row of the operators' audit log per action; the directory follows a block or ban."""
    event = received.event
    await record_action(session, received.event_id, received.occurred_at, event)
    action = ACCOUNT_ACTIONS.get(event.action)
    if action is not None:
        change = DIRECTORY_CHANGES[action]
        await follow_account(session, event.target_user_id, change, received.occurred_at)


SUBSCRIPTIONS: Final[tuple[EventSubscription[Any], ...]] = (
    EventSubscription(
        consumer="identity.directory_hides_deletion",
        event=AccountDeletionScheduled,
        queue=TaskQueue.DEFAULT,
        deadline=DEADLINE,
        handle=hide_in_directory,
        home=Home.EU,
    ),
    EventSubscription(
        consumer="identity.directory_shows_cancellation",
        event=AccountDeletionCancelled,
        queue=TaskQueue.DEFAULT,
        deadline=DEADLINE,
        handle=show_in_directory,
        home=Home.EU,
    ),
    EventSubscription(
        consumer="identity.operator_audit",
        event=OperatorActed,
        queue=TaskQueue.DEFAULT,
        deadline=DEADLINE,
        handle=audit_operator_action,
        home=Home.EU,
    ),
)

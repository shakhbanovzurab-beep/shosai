"""Asking for deletion, and cancelling it by signing in during the window (ID-D5).

The request needs the account's address typed again and a session started by a sign-in
less than 15 minutes ago. One home transaction then hides the account: its state, a new
token version, every session ended, the deletion row, the events and the mail naming the
date. A correct sign-in during the 7 days reverses the state in its own transaction, so
the data, hidden but unchanged, is shown again.
"""

from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import Insert, insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.email.messages import EmailKind, OutgoingEmail
from shosai.core.email.port import EmailPort
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.features.identity.application import native_errors
from shosai.features.identity.contracts import (
    AccountDeletionCancelled,
    AccountDeletionScheduled,
    Principal,
    SessionsRevoked,
)
from shosai.features.identity.domain.accounts import AccountState, SignInRefusal
from shosai.features.identity.domain.deletion import (
    DELETION_WINDOW,
    REAUTHENTICATION_WINDOW,
    DeletionState,
)
from shosai.features.identity.domain.emails import InvalidEmailError, normalize_email
from shosai.features.identity.emails.deletion_scheduled import DELETION_SCHEDULED_KEY
from shosai.features.identity.infrastructure.account_markers import AccountMarker, AccountMarkers
from shosai.features.identity.infrastructure.deletion_records import AccountDeletion
from shosai.features.identity.infrastructure.records import User
from shosai.features.identity.infrastructure.session_records import RefreshSession

REVOKE_REASON = "deletion"


class DeletionWindow:
    """Cancels a scheduled deletion inside the transaction of a correct sign-in."""

    def __init__(self, outbox: EventOutbox) -> None:
        self._outbox = outbox

    async def cancel_if_scheduled(self, session: AsyncSession, user: User) -> None:
        """Make a scheduled account active again; refuse one the saga already erases.

        The account row is locked first, as the saga's start locks it, so a sign-in at the
        last moment either cancels the deletion or finds the erasure begun.
        """
        if user.state != AccountState.DELETION_SCHEDULED:
            return
        await session.refresh(user, with_for_update=True)
        if user.state != AccountState.DELETION_SCHEDULED:
            raise native_errors.refused(SignInRefusal.DISABLED)
        now = datetime.now(UTC)
        user.state = AccountState.ACTIVE
        # Новая версия токена старше метки «удаление назначено», и новые токены проходят.
        user.token_version += 1
        await session.execute(
            update(AccountDeletion)
            .where(
                AccountDeletion.user_id == user.id,
                AccountDeletion.state == DeletionState.SCHEDULED.value,
            )
            .values(state=DeletionState.CANCELLED.value, cancelled_at=now)
        )
        await self._outbox.add(session, AccountDeletionCancelled(user_id=user.id))


class Deletions:
    """Schedules the deletion of the signed-in person's account."""

    def __init__(
        self,
        transactions: HomeTransactions,
        markers: AccountMarkers,
        outbox: EventOutbox,
        email: EmailPort,
    ) -> None:
        self._transactions = transactions
        self._markers = markers
        self._outbox = outbox
        self._email = email

    async def schedule(self, principal: Principal, confirm_email: str) -> datetime:
        """Hide the account now and set its erasure 7 days ahead; the erasure time."""
        now = datetime.now(UTC)
        erase_at = now + DELETION_WINDOW
        async with self._transactions.begin(principal.scope()) as session:
            user = await session.get(User, principal.user_id, with_for_update=True)
            if user is None:
                raise AppError("user_not_found", HTTPStatus.UNAUTHORIZED)
            if not _same_address(user.email, confirm_email):
                raise AppError("confirmation_mismatch", HTTPStatus.BAD_REQUEST)
            if not await _recent_sign_in(session, principal, now):
                raise AppError("reauthentication_required", HTTPStatus.FORBIDDEN)
            user.state = AccountState.DELETION_SCHEDULED
            user.token_version += 1
            await session.execute(
                update(RefreshSession)
                .where(RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None))
                .values(revoked_at=now, revoke_reason=REVOKE_REASON)
            )
            await session.execute(_scheduled(user.id, now, erase_at))
            await self._outbox.add(
                session, AccountDeletionScheduled(user_id=user.id, erase_at=erase_at)
            )
            await self._outbox.add(session, SessionsRevoked(user_id=user.id))
            await self._email.enqueue(
                session,
                OutgoingEmail(
                    recipient=user.email, kind=EmailKind.ACCOUNT,
                    template=DELETION_SCHEDULED_KEY, locale=user.language, user_id=user.id,
                    params={"date": erase_at.date().isoformat()},
                ),
            )  # fmt: skip
        marker = AccountMarker(user.token_version, AccountState.DELETION_SCHEDULED)
        await self._markers.write(user.id, marker)
        return erase_at


def _same_address(stored: str, typed: str) -> bool:
    try:
        return normalize_email(typed).value == stored
    except InvalidEmailError:
        return False


async def _recent_sign_in(session: AsyncSession, principal: Principal, now: datetime) -> bool:
    """Whether the request's session began with a sign-in in the last 15 minutes."""
    if principal.family_id is None:
        return False
    family = await session.get(RefreshSession, principal.family_id)
    return (
        family is not None
        and family.user_id == principal.user_id
        and family.revoked_at is None
        and family.created_at >= now - REAUTHENTICATION_WINDOW
    )


def _scheduled(user_id: UUID, now: datetime, erase_at: datetime) -> Insert:
    """The deletion row, written anew over a cancelled request of the same account."""
    values = {
        "state": DeletionState.SCHEDULED.value, "requested_at": now, "erase_at": erase_at,
        "run_at": erase_at, "cancelled_at": None, "started_at": None, "erased_owners": [],
    }  # fmt: skip
    return (
        insert(AccountDeletion)
        .values(user_id=user_id, **values)
        .on_conflict_do_update(index_elements=[AccountDeletion.user_id], set_=values)
    )

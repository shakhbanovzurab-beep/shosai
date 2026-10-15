"""The one account-state service: block and unblock (SM-12, ADR 0049, draft lesson in §1.2).

The draft froze and banned from two code paths, one without an audit row and neither with
a token version bump. Here one home transaction changes the state, bumps the version,
ends every session for a block, and writes the events and the audit event; after the
commit the Valkey marker turns every live access token into the 403 the native clients
read. The admin is not a person's account, so the audit event names no operator.
"""

from datetime import UTC, datetime
from http import HTTPStatus
from typing import Final
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.contracts import (
    AccountBlocked,
    AccountUnblocked,
    OperatorActed,
    OperatorAction,
    SessionsRevoked,
)
from shosai.features.identity.domain.account_actions import (
    TRANSITIONS,
    AccountAction,
    Transition,
)
from shosai.features.identity.domain.accounts import AccountState
from shosai.features.identity.infrastructure.account_markers import AccountMarker, AccountMarkers
from shosai.features.identity.infrastructure.directory import Directory
from shosai.features.identity.infrastructure.records import User
from shosai.features.identity.infrastructure.session_records import RefreshSession

# Как журнал аудита называет действие над аккаунтом.
AUDITED: Final = {
    AccountAction.BLOCK: OperatorAction.ACCOUNT_BLOCKED,
    AccountAction.UNBLOCK: OperatorAction.ACCOUNT_UNBLOCKED,
}


class AccountStates:
    """Applies the admin's action to an account in its home."""

    def __init__(
        self,
        transactions: HomeTransactions,
        directory: Directory,
        markers: AccountMarkers,
        outbox: EventOutbox,
    ) -> None:
        self._transactions = transactions
        self._directory = directory
        self._markers = markers
        self._outbox = outbox

    async def apply(self, user_id: UUID, action: AccountAction, reason_code: str) -> Home:
        """Change the account's state; the home it lives in. A repeat changes nothing."""
        home = await self._directory.home_of(user_id)
        if home is None:
            raise AppError("user_not_found", HTTPStatus.NOT_FOUND)
        transition = TRANSITIONS[action]
        async with self._transactions.begin(TenancyScope(home, user_id)) as session:
            user = await session.get(User, user_id, with_for_update=True)
            if user is None:
                raise AppError("user_not_found", HTTPStatus.NOT_FOUND)
            current = AccountState(user.state)
            if current is transition.target:
                return home
            if current not in transition.allowed_from:
                raise AppError("account_state_conflict", HTTPStatus.CONFLICT)
            user.state = transition.target
            user.token_version += 1
            await self._announce(session, user_id, action, transition)
            await self._outbox.add(
                session,
                OperatorActed(
                    target_user_id=user_id,
                    target_home=home,
                    action=AUDITED[action],
                    reason_code=reason_code,
                ),
            )
        await self._markers.write(user_id, AccountMarker(user.token_version, transition.target))
        return home

    async def _announce(
        self, session: AsyncSession, user_id: UUID, action: AccountAction, transition: Transition
    ) -> None:
        if not transition.ends_sessions:
            await self._outbox.add(session, AccountUnblocked(user_id=user_id))
            return
        await session.execute(
            update(RefreshSession)
            .where(RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC), revoke_reason=AUDITED[action].value)
        )
        await self._outbox.add(session, AccountBlocked(user_id=user_id))
        await self._outbox.add(session, SessionsRevoked(user_id=user_id))

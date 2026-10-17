"""Hiding a person's memberships while identity's deletion window runs (ADR 0053 point 4).

When identity schedules an account's deletion, its memberships become `hidden`: they keep
their seat and role, the person's shares stop being served (the policy admits a share
only while its sharer is active), and a cancellation brings them back unchanged. Each
workspace is changed in its own short transaction; a membership applies an account event
only if it is newer than the last one it applied, so events delivered out of order end
where the latest one says.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, case, or_, select, update

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.workspaces.domain.memberships import STANDING, MembershipState
from shosai.features.workspaces.infrastructure.organization_records import Membership


@dataclass(frozen=True, slots=True)
class AccountEvent:
    """An account's deletion was scheduled (`hidden`) or cancelled, at this moment."""

    home: Home
    user_id: UUID
    hidden: bool
    occurred_at: datetime


async def apply_account_event(transactions: HomeTransactions, event: AccountEvent) -> None:
    """Hide or show again every standing membership of the account; a repeat changes nothing."""
    target = MembershipState.HIDDEN if event.hidden else MembershipState.ACTIVE
    source = MembershipState.ACTIVE if event.hidden else MembershipState.HIDDEN
    async with transactions.begin(
        TenancyScope(event.home, event.user_id), read_only=True
    ) as session:
        found = await session.execute(
            select(Membership.org_id, Membership.id).where(
                Membership.user_id == event.user_id,
                Membership.state.in_([state.value for state in STANDING]),
            )
        )
        memberships = list(found)
    for org_id, membership_id in memberships:
        async with transactions.begin(TenancyScope(event.home, org_id=org_id)) as session:
            await session.execute(
                update(Membership)
                .where(
                    Membership.id == membership_id,
                    or_(
                        Membership.account_event_at.is_(None),
                        Membership.account_event_at < event.occurred_at,
                    ),
                )
                .values(
                    # Состояние меняется только из ожидаемого; время события пишется всегда.
                    state=_switch(source, target),
                    account_event_at=event.occurred_at,
                )
            )


def _switch(source: MembershipState, target: MembershipState) -> ColumnElement[str]:
    """`target` where the membership is in `source`, its own state otherwise."""
    return case((Membership.state == source, target.value), else_=Membership.state)

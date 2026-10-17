"""The invariant checks of workspaces: inv-14 and inv-16 (§16.4, workspaces plan §3.8).

**inv-14, hourly per home.** RLS shows a person only the rows of the workspaces they are
an active member of; the access policy must never open a workspace row beyond them. For
each shareable resource the check samples people with an active membership and, as the
sweep role (RLS off), counts the workspace rows the policy admits to them outside their
own workspaces. The gauge `shosai_workspaces_policy_rls_disagreements{home}` stays at
zero while policy and RLS agree.

**inv-16, daily per home.** A workspace's standing members and pending invitations never
exceed its paid seats. The gauge `shosai_workspaces_over_seats{home}` counts the
workspaces that do. Until billing binds its seats nobody joins, and the check only says so.

A home out of reach keeps its gauge as it was and says so in the log: an unread home must
not read as a clean one.
"""

from datetime import UTC, datetime
from typing import Final, Protocol
from uuid import UUID

import structlog
from prometheus_client import CollectorRegistry, Gauge
from sqlalchemy import ColumnElement, and_, func, not_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.access.shareable import ShareableResource
from shosai.core.db.errors import HomeUnavailableError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.workspaces.contracts import SEAT_ALLOWANCE, Viewer
from shosai.features.workspaces.domain.memberships import STANDING, MembershipState
from shosai.features.workspaces.domain.seats import SeatUse
from shosai.features.workspaces.infrastructure.access_records import Invitation
from shosai.features.workspaces.infrastructure.organization_records import (
    Membership,
    Organization,
)

# Столько людей с активным членством берётся в выборку за проход по каждому ресурсу.
SAMPLED_PEOPLE: Final = 50
log = structlog.stdlib.get_logger(__name__)


class ReadPredicate(Protocol):
    """The part of the access policy the self-test checks."""

    def readable(self, resource: ShareableResource, viewer: Viewer) -> ColumnElement[bool]:
        """The predicate that admits exactly the rows the viewer may read."""
        ...


class PolicySelfTest:
    """Counts workspace rows the policy opens beyond a person's own workspaces (inv-14)."""

    def __init__(
        self,
        transactions: HomeTransactions,
        policy: ReadPredicate,
        resources: tuple[ShareableResource, ...],
        registry: CollectorRegistry,
    ) -> None:
        self._transactions = transactions
        self._policy = policy
        self._resources = resources
        self._gauge = Gauge(
            "shosai_workspaces_policy_rls_disagreements",
            "Строки пространств, которые политика доступа открыла бы вне пространств человека",
            ("home",),
            registry=registry,
        )

    async def run(self, home: Home) -> int | None:
        """The disagreements found in the home; None when the home could not be read."""
        try:
            async with self._transactions.begin(
                TenancyScope(home), read_only=True, sweep=True
            ) as session:
                found = sum([await self._count(session, resource) for resource in self._resources])
        except HomeUnavailableError:
            log.warning("Самопроверка политики пропущена: дом недоступен", home=home.value)
            return None
        self._gauge.labels(home=home.value).set(found)
        if found:
            log.error(
                "Политика доступа открывает строки вне пространств человека",
                home=home.value,
                count=found,
            )
        return found

    async def _count(self, session: AsyncSession, resource: ShareableResource) -> int:
        people = await session.scalars(
            select(Membership.user_id)
            .where(Membership.state == MembershipState.ACTIVE)
            .group_by(Membership.user_id)
            .order_by(func.random())
            .limit(SAMPLED_PEOPLE)
        )
        org = resource.table.c[resource.org]
        total = 0
        for user_id in list(people):
            own = select(Membership.org_id).where(
                Membership.user_id == user_id, Membership.state == MembershipState.ACTIVE
            )
            beyond = and_(org.is_not(None), not_(org.in_(own)))
            query = (
                select(func.count())
                .select_from(resource.table)
                .where(beyond, self._policy.readable(resource, Viewer(user_id)))
            )
            total += await session.scalar(query) or 0
        return total


class SeatCheck:
    """Counts workspaces whose members and pending invitations exceed paid seats (inv-16)."""

    def __init__(
        self, transactions: HomeTransactions, ports: PortDirectory, registry: CollectorRegistry
    ) -> None:
        self._transactions = transactions
        self._ports = ports
        self._gauge = Gauge(
            "shosai_workspaces_over_seats",
            "Пространства, где участников и приглашений больше оплаченных мест",
            ("home",),
            registry=registry,
        )

    async def run(self, home: Home) -> int | None:
        """The workspaces over their seats in the home; None when it could not be checked."""
        bound = self._ports.all(SEAT_ALLOWANCE)
        if not bound:
            log.info("Проверка мест пропущена: billing ещё не продаёт места", home=home.value)
            return None
        try:
            async with self._transactions.begin(
                TenancyScope(home), read_only=True, sweep=True
            ) as session:
                over = 0
                for org_id in list(await session.scalars(select(Organization.id))):
                    paid = await bound[0].seats(session, org_id)
                    if not (await _use(session, org_id, paid.paid)).admits(0):
                        over += 1
                        log.error(
                            "У пространства больше людей, чем оплачено мест",
                            home=home.value,
                            org_id=str(org_id),
                        )
        except HomeUnavailableError:
            log.warning("Проверка мест пропущена: дом недоступен", home=home.value)
            return None
        self._gauge.labels(home=home.value).set(over)
        return over


async def _use(session: AsyncSession, org_id: UUID, paid: int) -> SeatUse:
    members = await session.scalar(
        select(func.count()).where(
            Membership.org_id == org_id, Membership.state.in_([state.value for state in STANDING])
        )
    )
    pending = await session.scalar(
        select(func.count()).where(
            Invitation.org_id == org_id,
            Invitation.accepted_at.is_(None),
            Invitation.expires_at > datetime.now(UTC),
        )
    )
    return SeatUse(paid, members or 0, pending or 0)

"""Operator roles: read on every admin request, changed by an owner (SM-12, identity plan §3.4).

Roles live in the person's home beside the account. A change replaces the person's set in
one home transaction with the audit event; the audit row itself is written in the EU by
the event's delivery, since no transaction spans two homes. Changes take one platform-wide
lock, so the count of owners across both homes stays true while the last one is guarded.
"""

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta
from http import HTTPStatus
from typing import Final
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.kv.locks import DistributedLocks, LockOutagePolicy
from shosai.features.identity.contracts import (
    Operator,
    OperatorActed,
    OperatorAction,
    OperatorRole,
    Principal,
)
from shosai.features.identity.domain.accounts import AccountState
from shosai.features.identity.domain.registration import DirectoryState
from shosai.features.identity.infrastructure.directory import Directory
from shosai.features.identity.infrastructure.operator_records import OperatorRoleGrant
from shosai.features.identity.infrastructure.records import User

OPERATORS_LOCK: Final = "identity.operators"
LOCK_TTL: Final = timedelta(seconds=30)


@dataclass(frozen=True, slots=True)
class OperatorView:
    """An operator as the owner's screen lists them."""

    user_id: UUID
    home: Home
    email: str
    full_name: str
    roles: frozenset[OperatorRole]


class OperatorRoles:
    """The `identity.operator_roles` port: the roles of the request's person, read now."""

    def __init__(self, transactions: HomeTransactions) -> None:
        self._transactions = transactions

    async def roles_of(self, principal: Principal) -> frozenset[OperatorRole]:
        """The person's roles in their home; empty for everyone else."""
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            return await held_roles(session, principal.user_id)


class Operators:
    """Lists the operators of both homes and changes a person's roles."""

    def __init__(
        self,
        transactions: HomeTransactions,
        directory: Directory,
        outbox: EventOutbox,
        locks: DistributedLocks,
    ) -> None:
        self._transactions = transactions
        self._directory = directory
        self._outbox = outbox
        self._locks = locks

    async def everyone(self) -> list[OperatorView]:
        """Every operator of both homes, by name."""
        found = await asyncio.gather(*(self._operators_in(home) for home in Home))
        return sorted((view for views in found for view in views), key=_by_name)

    async def set_roles(
        self, actor: Operator | None, user_id: UUID, roles: frozenset[OperatorRole]
    ) -> OperatorView:
        """Replace the person's roles; the last owner keeps the owner role.

        `actor` is None for the first owner, granted by `shosai identity grant-operator`.
        """
        home = await self._directory.home_of(user_id)
        if home is None:
            raise AppError("user_not_found", HTTPStatus.NOT_FOUND)
        async with self._locks.hold(
            OPERATORS_LOCK, ttl=LOCK_TTL, outage=LockOutagePolicy.FAIL_CLOSED
        ) as lease:
            if lease is None:
                raise AppError("operators_busy", HTTPStatus.CONFLICT)
            if OperatorRole.OWNER not in roles and not await self._other_owner(user_id):
                await self._refuse_last_owner(home, user_id)
            return await self._replace(actor, home, user_id, roles)

    async def grant(self, address_hmac: bytes, role: OperatorRole) -> OperatorView:
        """Add one role to the active account of an address: the first owner, from the CLI."""
        record = await self._directory.find_fresh(address_hmac)
        if record is None or record.state is not DirectoryState.ACTIVE:
            raise AppError("user_not_found", HTTPStatus.NOT_FOUND)
        scope = TenancyScope(record.home, record.user_id)
        async with self._transactions.begin(scope, read_only=True) as session:
            current = await held_roles(session, record.user_id)
        return await self.set_roles(None, record.user_id, current | {role})

    async def _replace(
        self, actor: Operator | None, home: Home, user_id: UUID, roles: frozenset[OperatorRole]
    ) -> OperatorView:
        async with self._transactions.begin(TenancyScope(home, user_id)) as session:
            user = await session.get(User, user_id, with_for_update=True)
            if user is None:
                raise AppError("user_not_found", HTTPStatus.NOT_FOUND)
            if roles and user.state != AccountState.ACTIVE:
                raise AppError("account_not_active", HTTPStatus.CONFLICT)
            if await held_roles(session, user_id) != roles:
                granted_by = actor.principal.user_id if actor else None
                await session.execute(
                    delete(OperatorRoleGrant).where(OperatorRoleGrant.user_id == user_id)
                )
                session.add_all(
                    OperatorRoleGrant(user_id=user_id, role=role.value, granted_by=granted_by)
                    for role in sorted(roles)
                )
                await self._outbox.add(
                    session,
                    OperatorActed(
                        operator_id=granted_by, target_user_id=user_id, target_home=home,
                        action=OperatorAction.ROLES_CHANGED,
                    ),
                )  # fmt: skip
            return OperatorView(user_id, home, user.email, user.full_name, roles)

    async def _other_owner(self, user_id: UUID) -> bool:
        counts = await asyncio.gather(*(self._owners_besides(home, user_id) for home in Home))
        return sum(counts) > 0

    async def _owners_besides(self, home: Home, user_id: UUID) -> int:
        async with self._transactions.begin(TenancyScope(home), read_only=True) as session:
            owners = await session.scalar(
                select(func.count()).where(
                    OperatorRoleGrant.role == OperatorRole.OWNER.value,
                    OperatorRoleGrant.user_id != user_id,
                )
            )
        return owners or 0

    async def _refuse_last_owner(self, home: Home, user_id: UUID) -> None:
        async with self._transactions.begin(TenancyScope(home, user_id), read_only=True) as session:
            if OperatorRole.OWNER in await held_roles(session, user_id):
                raise AppError("last_owner", HTTPStatus.CONFLICT)

    async def _operators_in(self, home: Home) -> list[OperatorView]:
        async with self._transactions.begin(TenancyScope(home), read_only=True) as session:
            rows = await session.execute(
                select(User.id, User.email, User.full_name, OperatorRoleGrant.role)
                .join(OperatorRoleGrant, OperatorRoleGrant.user_id == User.id)
                .order_by(User.id)
            )
            grouped: dict[UUID, tuple[str, str, list[OperatorRole]]] = {}
            for user_id, email, name, role in rows:
                grouped.setdefault(user_id, (email, name, []))[2].append(OperatorRole(role))
        return [
            OperatorView(user_id, home, email, name, frozenset(roles))
            for user_id, (email, name, roles) in grouped.items()
        ]


async def held_roles(session: AsyncSession, user_id: UUID) -> frozenset[OperatorRole]:
    """The roles a person holds, read in the caller's transaction of their home."""
    roles: Iterable[str] = await session.scalars(
        select(OperatorRoleGrant.role).where(OperatorRoleGrant.user_id == user_id)
    )
    return frozenset(OperatorRole(role) for role in roles)


def _by_name(view: OperatorView) -> tuple[str, str]:
    return view.full_name.casefold(), str(view.user_id)

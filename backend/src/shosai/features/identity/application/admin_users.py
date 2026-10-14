"""Finding a person and reading their card, for support (identity plan §3.4, SM-12).

By exact email the directory names the one home to read. By name both homes are read in
parallel and merged, newest account first: each home pages by id after the cursor, the
merge keeps the first `limit + 1`, so a page is the same whichever home holds the rows.
The card adds the live sessions, the latest sign-ins, the AI spend of today, the week and
the month over both homes (F6; cost rows stay where they were written) and the roles.
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any, Final, cast
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Row, Select, Table, or_, select

from shosai.core.ai.spend.reports import ZERO, SpendReports, UserSpend
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.pagination.cursor import CursorCodec
from shosai.core.pagination.keyset import Keyset
from shosai.core.pagination.page import Page, PageRequest, page_of
from shosai.features.identity.application.operators import held_roles
from shosai.features.identity.contracts import OperatorRole
from shosai.features.identity.domain.accounts import AccountState
from shosai.features.identity.domain.directory import email_hmac
from shosai.features.identity.domain.emails import InvalidEmailError, normalize_email
from shosai.features.identity.domain.registration import NOT_ACCOUNTS
from shosai.features.identity.infrastructure.directory import Directory
from shosai.features.identity.infrastructure.records import User
from shosai.features.identity.infrastructure.session_records import LoginEvent, RefreshSession

CARD_ROWS: Final = 20
USERS: Final = cast("Table", User.__table__)
NEWEST_FIRST: Final = Keyset((USERS.c.id,), descending=True)
SUMMARY: Final = (
    USERS.c.id, USERS.c.email, USERS.c.full_name, USERS.c.display_name, USERS.c.state,
    USERS.c.created_at, USERS.c.last_login_at,
)  # fmt: skip


class UserPosition(BaseModel):
    """Where a page of the search ends."""

    id: UUID


CODEC: Final = CursorCodec("identity.admin_users", UserPosition)


@dataclass(frozen=True, slots=True)
class UserSummary:
    """A found account."""

    id: UUID
    home: Home
    email: str
    full_name: str
    display_name: str | None
    state: AccountState
    created_at: datetime
    last_login_at: datetime | None


@dataclass(frozen=True, slots=True)
class UserCard:
    """What support sees of one account."""

    summary: UserSummary
    user: User
    sessions: Sequence[RefreshSession]
    sign_ins: Sequence[LoginEvent]
    spend: UserSpend
    operator_roles: frozenset[OperatorRole]


class AdminUsers:
    """Search and cards over both homes."""

    def __init__(
        self,
        transactions: HomeTransactions,
        directory: tuple[Directory, bytes],
        reports: SpendReports,
    ) -> None:
        self._transactions = transactions
        self._directory, self._directory_key = directory
        self._reports = reports

    async def by_email(self, address: str) -> Page[UserSummary]:
        """The one account of an address, from the home the directory names."""
        try:
            normalized = normalize_email(address)
        except InvalidEmailError:
            return Page(items=[], next_cursor=None)
        record = await self._directory.find_fresh(email_hmac(self._directory_key, normalized))
        if record is None or record.state in NOT_ACCOUNTS:
            return Page(items=[], next_cursor=None)
        query: Select[tuple[Any, ...]] = select(*SUMMARY).where(USERS.c.id == record.user_id)
        async with self._transactions.begin(TenancyScope(record.home), read_only=True) as session:
            rows = (await session.execute(query)).all()
        return Page(items=[_summary(row, record.home) for row in rows], next_cursor=None)

    async def by_name(self, text: str, request: PageRequest) -> Page[UserSummary]:
        """Accounts whose full or display name contains the text, newest first."""
        pattern = f"%{_escaped(text)}%"
        after = None if request.cursor is None else (CODEC.decode(request.cursor).id,)
        found = await asyncio.gather(
            *(self._named_in(home, pattern, after, request.limit) for home in Home)
        )
        merged = sorted(
            (pair for pairs in found for pair in pairs), key=lambda pair: pair[0].id, reverse=True
        )
        return page_of(
            merged[: request.limit + 1], request, CODEC,
            lambda pair: _summary(*pair), lambda pair: UserPosition(id=pair[0].id),
        )  # fmt: skip

    async def card(self, user_id: UUID) -> UserCard:
        """The account, its sessions, sign-ins, AI spend and operator roles."""
        home = await self._directory.home_of(user_id)
        if home is None:
            raise AppError("user_not_found", HTTPStatus.NOT_FOUND)
        async with self._transactions.begin(TenancyScope(home, user_id), read_only=True) as session:
            user = await session.get(User, user_id)
            if user is None:
                raise AppError("user_not_found", HTTPStatus.NOT_FOUND)
            sessions = (
                await session.scalars(
                    select(RefreshSession)
                    .where(RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None))
                    .order_by(RefreshSession.last_used_at.desc())
                    .limit(CARD_ROWS)
                )
            ).all()
            sign_ins = (
                await session.scalars(
                    select(LoginEvent)
                    .where(LoginEvent.user_id == user_id)
                    .order_by(LoginEvent.created_at.desc())
                    .limit(CARD_ROWS)
                )
            ).all()
            roles = await held_roles(session, user_id)
        at = datetime.now(UTC)
        # Строки расходов остаются в доме, где записаны: после переноса их два.
        homes_spend = await asyncio.gather(
            *(self._reports.user_spend(each, user_id, at) for each in Home)
        )
        spend = UserSpend(
            sum((part.today_usd for part in homes_spend), ZERO),
            sum((part.week_usd for part in homes_spend), ZERO),
            sum((part.month_usd for part in homes_spend), ZERO),
        )
        summary = UserSummary(
            user.id, home, user.email, user.full_name, user.display_name,
            AccountState(user.state), user.created_at, user.last_login_at,
        )  # fmt: skip
        return UserCard(summary, user, sessions, sign_ins, spend, roles)

    async def _named_in(
        self, home: Home, pattern: str, after: tuple[UUID] | None, limit: int
    ) -> list[tuple[Row[Any], Home]]:
        named: Select[tuple[Any, ...]] = select(*SUMMARY).where(
            or_(USERS.c.full_name.ilike(pattern), USERS.c.display_name.ilike(pattern)),
            USERS.c.state != AccountState.DELETED.value,
        )
        statement = NEWEST_FIRST.page(named, after, limit)
        async with self._transactions.begin(TenancyScope(home), read_only=True) as session:
            rows = (await session.execute(statement)).all()
        return [(row, home) for row in rows]


def _escaped(text: str) -> str:
    """The text as a literal inside LIKE: its wildcards and the escape stand for themselves."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _summary(row: Row[Any], home: Home) -> UserSummary:
    return UserSummary(
        row.id, home, row.email, row.full_name, row.display_name, AccountState(row.state),
        row.created_at, row.last_login_at,
    )  # fmt: skip

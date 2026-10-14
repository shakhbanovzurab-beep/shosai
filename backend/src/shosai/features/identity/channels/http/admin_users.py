"""Accounts for support: search, the card, block, unblock and ban (`/v1/admin/users*`, SM-12).

Owners, support and read-only operators search and read; owners and support act. Each
action answers the card as it is after the action and leaves one row in the audit log.
"""

from datetime import datetime
from decimal import Decimal
from http import HTTPStatus
from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from shosai.core.kernel.errors import AppError
from shosai.core.pagination.page import Page, PageParameters
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.application.account_states import AccountStates
from shosai.features.identity.application.admin_users import AdminUsers, UserCard, UserSummary
from shosai.features.identity.contracts import Operator, OperatorRole, require_operator
from shosai.features.identity.domain.account_actions import AccountAction
from shosai.features.identity.domain.accounts import AccountState

READERS: Final = (OperatorRole.OWNER, OperatorRole.SUPPORT, OperatorRole.READ_ONLY)
ACTORS: Final = (OperatorRole.OWNER, OperatorRole.SUPPORT)


class AdminUser(BaseModel):
    """A found account and the home it lives in."""

    id: UUID
    home: str
    email: str
    full_name: str
    display_name: str | None
    state: AccountState
    created_at: datetime
    last_login_at: datetime | None


class AdminSession(BaseModel):
    """A live session of the account."""

    id: UUID
    client_kind: str
    device_label: str | None
    ip: str | None
    created_at: datetime
    last_used_at: datetime


class AdminSignIn(BaseModel):
    """A sign-in attempt and how it ended."""

    created_at: datetime
    outcome: str
    client_kind: str
    ip: str | None


class AdminSpend(BaseModel):
    """The account's AI spend in USD, UTC periods."""

    today_usd: Decimal
    week_usd: Decimal
    month_usd: Decimal


class AdminUserCard(BaseModel):
    """What support sees of one account."""

    user: AdminUser
    work_role: str | None
    country: str | None
    language: str
    timezone: str | None
    email_verified_at: datetime | None
    sessions: list[AdminSession]
    sign_ins: list[AdminSignIn]
    spend: AdminSpend
    operator_roles: list[OperatorRole]


class ActionReason(BaseModel):
    """Why the operator acts, as a code the audit log keeps."""

    model_config = ConfigDict(extra="forbid")

    reason_code: Annotated[str, Field(pattern=r"^[a-z0-9_.:-]{1,64}$")]


def user_of(summary: UserSummary) -> AdminUser:
    """The answer of a found account."""
    return AdminUser(
        id=summary.id, home=summary.home.value, email=summary.email,
        full_name=summary.full_name, display_name=summary.display_name, state=summary.state,
        created_at=summary.created_at, last_login_at=summary.last_login_at,
    )  # fmt: skip


def card_of(card: UserCard) -> AdminUserCard:
    """The answer of a card."""
    user = card.user
    return AdminUserCard(
        user=user_of(card.summary), work_role=user.work_role, country=user.country,
        language=user.language, timezone=user.timezone, email_verified_at=user.email_verified_at,
        sessions=[
            AdminSession(
                id=item.id, client_kind=item.client_kind, device_label=item.device_label,
                ip=None if item.ip is None else str(item.ip), created_at=item.created_at,
                last_used_at=item.last_used_at,
            )
            for item in card.sessions
        ],
        sign_ins=[
            AdminSignIn(
                created_at=item.created_at, outcome=item.outcome, client_kind=item.client_kind,
                ip=None if item.ip is None else str(item.ip),
            )
            for item in card.sign_ins
        ],
        spend=AdminSpend(
            today_usd=card.spend.today_usd, week_usd=card.spend.week_usd,
            month_usd=card.spend.month_usd,
        ),
        operator_roles=sorted(card.operator_roles),
    )  # fmt: skip


def build_admin_users_router(
    users: AdminUsers, states: AccountStates, ports: PortDirectory
) -> APIRouter:
    """Support's routes over accounts."""
    router = APIRouter(prefix="/v1/admin/users", tags=["admin"])
    reader = Annotated[Operator, Depends(require_operator(ports, *READERS))]
    actor = Annotated[Operator, Depends(require_operator(ports, *ACTORS))]

    @router.get("")
    async def search_users(
        _operator: reader,
        page: PageParameters,
        email: Annotated[str | None, Query(max_length=254)] = None,
        name: Annotated[str | None, Query(min_length=2, max_length=80)] = None,
    ) -> Page[AdminUser]:
        """By exact email, or by a part of the full or display name in both homes."""
        if (email is None) == (name is None):
            raise AppError("search_needs_email_or_name", HTTPStatus.UNPROCESSABLE_ENTITY)
        found = await (users.by_email(email) if email else users.by_name(name or "", page))
        return Page(items=[user_of(item) for item in found.items], next_cursor=found.next_cursor)

    @router.get("/{user_id}")
    async def read_user(user_id: UUID, _operator: reader) -> AdminUserCard:
        """The card: profile, state, sessions, sign-ins, AI spend and operator roles."""
        return card_of(await users.card(user_id))

    async def acted(
        operator: Operator, user_id: UUID, action: AccountAction, reason: str
    ) -> AdminUserCard:
        await states.apply(operator, user_id, action, reason)
        return card_of(await users.card(user_id))

    @router.post("/{user_id}/block")
    async def block_user(user_id: UUID, body: ActionReason, operator: actor) -> AdminUserCard:
        """Freeze the account: every session ends, sign-in is refused until unblocked."""
        return await acted(operator, user_id, AccountAction.BLOCK, body.reason_code)

    @router.post("/{user_id}/unblock")
    async def unblock_user(user_id: UUID, body: ActionReason, operator: actor) -> AdminUserCard:
        """Return a frozen account; a banned one stays banned (409)."""
        return await acted(operator, user_id, AccountAction.UNBLOCK, body.reason_code)

    @router.post("/{user_id}/ban")
    async def ban_user(user_id: UUID, body: ActionReason, operator: actor) -> AdminUserCard:
        """Close the account for good: every session ends, the address cannot register again."""
        return await acted(operator, user_id, AccountAction.BAN, body.reason_code)

    return router

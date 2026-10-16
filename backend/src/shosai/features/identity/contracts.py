"""What other slices may use of identity (identity plan §3.3, ADR 0045).

Other slices reach identity's services through the port keys below and
`CoreServices.ports`; they never import identity's internals. Identity binds these ports
in the steps that build them: the authenticator with sign-in, consents and the profile
with Settings. Events carry ids only (§12).
"""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from http import HTTPStatus
from typing import Annotated, ClassVar, Final, Protocol
from uuid import UUID

from fastapi import Cookie, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.domain_event import DomainEvent, EventCode
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.core.ports.keys import Cardinality, PortKey
from shosai.core.web.request_facts import note_caller


@dataclass(frozen=True, slots=True)
class Principal:
    """The person a request or a WebSocket acts for, from a verified access token."""

    user_id: UUID
    home: Home
    token_version: int
    # Сессия (семейство refresh) устройства; None у токенов черновика.
    family_id: UUID | None = None

    def scope(self) -> TenancyScope:
        """The tenancy scope of the person's own transactions, in their home."""
        return TenancyScope(home=self.home, user_id=self.user_id)


class AdminGate(Protocol):
    """Checks the admin's session cookie on every admin request (ADR 0049)."""

    async def admitted(self, cookie: str | None) -> bool:
        """Whether the cookie belongs to a live admin session."""
        ...


class OperatorAction(StrEnum):
    """What the admin did; the audit log keeps it for 12 months (nfr-17)."""

    ACCOUNT_BLOCKED = "account_blocked"
    ACCOUNT_UNBLOCKED = "account_unblocked"
    ACCOUNT_TRANSFER_REQUESTED = "account_transfer_requested"
    ACCOUNT_TRANSFER_CANCELLED = "account_transfer_cancelled"


class Authenticator(Protocol):
    """Turns a bearer token into the person it acts for; one resolver for HTTP and WS."""

    async def principal(self, bearer_token: str) -> Principal:
        """The person of a valid access token; raises the API error the client reads."""
        ...


class ConsentReader(Protocol):
    """Cross-border consent (nfr-14), read in the caller's transaction for its `CallContext`."""

    async def cross_border(self, session: AsyncSession, user_id: UUID) -> bool:
        """Whether the person currently consents to transfer to providers abroad."""
        ...


@dataclass(frozen=True, slots=True)
class AccountProfile:
    """How the person is addressed: by Leo, in emails, in the language they chose."""

    display_name: str
    language: str
    timezone: str | None


class AccountProfileReader(Protocol):
    """The person's profile, read in the caller's transaction."""

    async def profile(self, session: AsyncSession, user_id: UUID) -> AccountProfile | None:
        """The profile, or None for an account that no longer exists."""
        ...


class MeContribution(Protocol):
    """A slice's part of the native `GET /v1/auth/me` (billing, meetings, memory, agent).

    Each returns the fields it owns, by the names and shapes of the draft contract; fields
    no slice contributes keep the draft's defaults (identity plan §3.3).
    """

    async def native_me(self, principal: Principal) -> Mapping[str, object]:
        """The fields of `UserMeResponse` this slice owns, for the person."""
        ...


AUTHENTICATOR: Final = PortKey[Authenticator]("identity.authenticator")
ME_CONTRIBUTIONS: Final = PortKey[MeContribution]("identity.me_contribution", Cardinality.MANY)
CONSENT_READER: Final = PortKey[ConsentReader]("identity.consent_reader")
ACCOUNT_PROFILE_READER: Final = PortKey[AccountProfileReader]("identity.account_profile_reader")
ADMIN_GATE: Final = PortKey[AdminGate]("identity.admin_gate")
BEARER: Final = "Bearer "
ADMIN_COOKIE: Final = "shosai_admin"
ADMIN_COOKIE_LENGTH: Final = 256


def bearer_principal(ports: PortDirectory) -> Callable[..., Awaitable[Principal]]:
    """A route dependency: the person of the request's bearer token, through identity.

    Missing or malformed, the header is 401 `Missing Bearer token`, the draft's `detail`
    that native clients read; everything else is the authenticator's answer. The person's
    home and id go to the request's metrics, span and log lines (`note_caller`).
    """

    async def authenticated(
        request: Request, authorization: Annotated[str | None, Header()] = None
    ) -> Principal:
        if not authorization or not authorization.startswith(BEARER):
            raise AppError("unauthorized", HTTPStatus.UNAUTHORIZED, detail="Missing Bearer token")
        principal = await ports.get(AUTHENTICATOR).principal(authorization.removeprefix(BEARER))
        # Дом и человек запроса — метке home HTTP-метрики, строке доступа и логам (§16.2).
        note_caller(request, principal.home, principal.user_id)
        return principal

    return authenticated


def require_admin(ports: PortDirectory) -> Callable[..., Awaitable[None]]:
    """A route dependency: the admin's live session, from its cookie (ADR 0049).

    Unrelated to people's accounts and tokens; without the session the answer is 401
    `admin_sign_in_required`.
    """

    async def admin(
        cookie: Annotated[
            str | None, Cookie(alias=ADMIN_COOKIE, max_length=ADMIN_COOKIE_LENGTH)
        ] = None,
    ) -> None:
        if not await ports.get(ADMIN_GATE).admitted(cookie):
            raise AppError("admin_sign_in_required", HTTPStatus.UNAUTHORIZED)

    return admin


class AccountRegistered(DomainEvent):
    """A person verified their email and the account exists in its home."""

    event_type: ClassVar[str] = "identity.account.registered"
    version: ClassVar[int] = 1
    user_id: UUID


class AccountDeletionScheduled(DomainEvent):
    """The person asked for deletion: hide their data from everyone until `erase_at`."""

    event_type: ClassVar[str] = "identity.account.deletion_scheduled"
    version: ClassVar[int] = 1
    user_id: UUID
    erase_at: datetime


class AccountDeletionCancelled(DomainEvent):
    """The person signed in during the window: show their data again, unchanged."""

    event_type: ClassVar[str] = "identity.account.deletion_cancelled"
    version: ClassVar[int] = 1
    user_id: UUID


class AccountDeleted(DomainEvent):
    """Every registered owner erased the person's data; the account is anonymised."""

    event_type: ClassVar[str] = "identity.account.deleted"
    version: ClassVar[int] = 1
    user_id: UUID


class AccountTransferred(DomainEvent):
    """The account and its data now live in another home."""

    event_type: ClassVar[str] = "identity.account.transferred"
    version: ClassVar[int] = 1
    user_id: UUID
    from_home: Home
    to_home: Home


class AccountBlocked(DomainEvent):
    """The admin froze the account; its sessions ended."""

    event_type: ClassVar[str] = "identity.account.blocked"
    version: ClassVar[int] = 1
    user_id: UUID


class AccountUnblocked(DomainEvent):
    """The admin returned a frozen account; it signs in again, its data is shown again."""

    event_type: ClassVar[str] = "identity.account.unblocked"
    version: ClassVar[int] = 1
    user_id: UUID


class SessionsRevoked(DomainEvent):
    """Some or all sessions of the person ended; open sockets of those sessions close."""

    event_type: ClassVar[str] = "identity.sessions.revoked"
    version: ClassVar[int] = 1
    user_id: UUID


class OperatorActed(DomainEvent):
    """The admin changed an account; the EU audit log records it."""

    event_type: ClassVar[str] = "identity.operator.acted"
    version: ClassVar[int] = 1
    # Пусто: админ один и входит не аккаунтом человека (ADR 0049). Поле остаётся ради строк
    # журнала, записанных до этого решения.
    operator_id: UUID | None = None
    target_user_id: UUID
    target_home: Home
    action: OperatorAction
    reason_code: EventCode | None = None


IDENTITY_EVENTS: Final[tuple[type[DomainEvent], ...]] = (
    AccountRegistered,
    AccountDeletionScheduled,
    AccountDeletionCancelled,
    AccountDeleted,
    AccountTransferred,
    AccountBlocked,
    AccountUnblocked,
    SessionsRevoked,
    OperatorActed,
)

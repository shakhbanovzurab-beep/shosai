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

from fastapi import Header
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.domain_event import DomainEvent
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.core.ports.keys import Cardinality, PortKey


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


class OperatorRole(StrEnum):
    """The fixed operator roles; each `/v1/admin/*` router names the ones it admits (SM-12)."""

    OWNER = "owner"
    SUPPORT = "support"
    FINANCE = "finance"
    PLATFORM = "platform"
    RELEASES = "releases"
    READ_ONLY = "read_only"


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
BEARER: Final = "Bearer "


def bearer_principal(ports: PortDirectory) -> Callable[..., Awaitable[Principal]]:
    """A route dependency: the person of the request's bearer token, through identity.

    Missing or malformed, the header is 401 `Missing Bearer token`, the draft's `detail`
    that native clients read; everything else is the authenticator's answer.
    """

    async def authenticated(authorization: Annotated[str | None, Header()] = None) -> Principal:
        if not authorization or not authorization.startswith(BEARER):
            raise AppError("unauthorized", HTTPStatus.UNAUTHORIZED, detail="Missing Bearer token")
        return await ports.get(AUTHENTICATOR).principal(authorization.removeprefix(BEARER))

    return authenticated


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
    """An operator froze or banned the account; its sessions ended."""

    event_type: ClassVar[str] = "identity.account.blocked"
    version: ClassVar[int] = 1
    user_id: UUID


class SessionsRevoked(DomainEvent):
    """Some or all sessions of the person ended; open sockets of those sessions close."""

    event_type: ClassVar[str] = "identity.sessions.revoked"
    version: ClassVar[int] = 1
    user_id: UUID


IDENTITY_EVENTS: Final[tuple[type[DomainEvent], ...]] = (
    AccountRegistered,
    AccountDeletionScheduled,
    AccountDeletionCancelled,
    AccountDeleted,
    AccountTransferred,
    AccountBlocked,
    SessionsRevoked,
)

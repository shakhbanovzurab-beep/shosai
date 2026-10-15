"""Social sign-in: start at a provider, come back, finish in the cabinet (ADR 0045 point 10).

The callback never answers JSON: every outcome is a redirect to the cabinet's sign-in
page, with a one-time session ticket for a known person (`social`), an encrypted consent
ticket for a new one (`social_consent`), or an error code (`social_error`). The person
is found by the provider's user id in either home; failing that, by an address the
provider proved, in the directory; a provider that proves nothing (VK) never links to an
existing account by itself.
"""

import asyncio
import secrets
from dataclasses import dataclass
from typing import Final
from urllib.parse import urlencode
from uuid import UUID

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.domain.accounts import AccountState, sign_in_refusal
from shosai.features.identity.domain.directory import email_hmac
from shosai.features.identity.domain.emails import InvalidEmailError, normalize_email
from shosai.features.identity.domain.pkce import challenge_of
from shosai.features.identity.domain.registration import NOT_ACCOUNTS, DirectoryState
from shosai.features.identity.domain.social import (
    Provider,
    SocialIdentity,
    safe_next,
    sign_state,
    state_nonce,
)
from shosai.features.identity.infrastructure.directory import Directory
from shosai.features.identity.infrastructure.records import User, UserIdentity
from shosai.features.identity.infrastructure.social.base import SocialProvider
from shosai.features.identity.infrastructure.social.consent_tickets import (
    ConsentClaim,
    ConsentTickets,
)
from shosai.features.identity.infrastructure.social.flows import Flow, SessionTicket, SocialStates

LOGIN_PAGE: Final = "/app/login"
log = structlog.stdlib.get_logger(__name__)


class SocialRefusedError(Exception):
    """An outcome the cabinet shows by its code; never a server fault."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class WidgetFlow:
    """What a provider's code widget (VK ID OneTap) needs to start.

    The signed state, the PKCE challenge and the redirect URI the provider checks in the exchange.
    """

    state: str
    code_challenge: str
    redirect_uri: str


@dataclass(frozen=True, slots=True)
class Outcome:
    """Exactly one of a session ticket, a consent ticket, with the return path."""

    session_ticket: str | None
    consent_ticket: str | None
    next_path: str


@dataclass(frozen=True, slots=True)
class SocialServices:
    """What social sign-in works with."""

    transactions: HomeTransactions
    directory: Directory
    states: SocialStates
    consent: ConsentTickets
    providers: dict[Provider, SocialProvider]
    state_key: bytes
    directory_key: bytes
    base_url: str


class SocialSignIn:
    """Start, come back, resolve the person."""

    def __init__(self, services: SocialServices) -> None:
        self._services = services

    async def start(self, provider: Provider, next_path: str | None, language: str) -> str:
        """The provider's URL for a new flow; its state lives 10 minutes."""
        client = self._client(provider)
        nonce, state = sign_state(self._services.state_key)
        verifier = secrets.token_urlsafe(48)
        await self._services.states.open_flow(
            nonce, Flow(provider, verifier, safe_next(next_path), language)
        )
        return client.authorize_url(state, challenge_of(verifier))

    async def widget_flow(
        self, provider: Provider, next_path: str | None, language: str
    ) -> WidgetFlow:
        """A flow for a code widget: the verifier stays here, the widget gets its hash."""
        client = self._client(provider)
        redirect_uri = getattr(client, "widget_redirect_uri", None)
        if not isinstance(redirect_uri, str):
            raise SocialRefusedError("social_provider_disabled")
        nonce, state = sign_state(self._services.state_key)
        verifier = secrets.token_urlsafe(48)
        await self._services.states.open_flow(
            nonce, Flow(provider, verifier, safe_next(next_path), language)
        )
        return WidgetFlow(state, challenge_of(verifier), redirect_uri)

    async def callback(
        self, provider: Provider, code: str, state: str, device_id: str | None
    ) -> Outcome:
        """Resolve the person a provider sent back; `SocialRefusedError` for the page."""
        nonce = state_nonce(self._services.state_key, state)
        flow = None if nonce is None else await self._services.states.take_flow(nonce)
        if flow is None or flow.provider is not provider:
            raise SocialRefusedError("social_state_invalid")
        identity = await self._client(provider).identify(code, flow.verifier, device_id)
        return await self.resolve(identity, flow.next_path, flow.language)

    async def resolve(self, identity: SocialIdentity, next_path: str, language: str) -> Outcome:
        """A session ticket for a known person, a consent ticket for a new one."""
        linked = await self._linked(identity)
        if linked is None:
            linked = await self._by_proven_email(identity)
        if linked is not None:
            ticket = secrets.token_urlsafe(32)
            await self._services.states.issue_ticket(ticket, SessionTicket(*linked, next_path))
            return Outcome(ticket, None, next_path)
        if identity.email is None:
            raise SocialRefusedError("social_email_required")
        claim = ConsentClaim(identity, next_path, language)
        return Outcome(None, self._services.consent.seal(claim), next_path)

    def enabled(self, provider: Provider) -> bool:
        """Whether this deployment has the provider's credentials."""
        return provider in self._services.providers

    async def widget(
        self, provider: Provider, token: str, next_path: str | None, language: str
    ) -> Outcome:
        """Resolve the person behind a widget token (Yandex's, Google's)."""
        client = self._client(provider)
        identify_token = getattr(client, "identify_token", None)
        if identify_token is None:
            raise SocialRefusedError("social_provider_disabled")
        identity = await identify_token(token)
        return await self.resolve(identity, safe_next(next_path), language)

    def redirect(self, outcome: Outcome | None, error: str | None, provider: Provider) -> str:
        """The cabinet's sign-in page with the outcome in its query."""
        query: dict[str, str] = {}
        if error is not None:
            query["social_error"] = error
        elif outcome is not None and outcome.session_ticket is not None:
            query["social"] = outcome.session_ticket
        elif outcome is not None and outcome.consent_ticket is not None:
            query["social_consent"] = outcome.consent_ticket
            query["social_provider"] = provider.value
        if outcome is not None and outcome.next_path:
            query["next"] = outcome.next_path
        return f"{self._services.base_url}{LOGIN_PAGE}?{urlencode(query)}"

    def _client(self, provider: Provider) -> SocialProvider:
        client = self._services.providers.get(provider)
        if client is None:
            raise SocialRefusedError("social_provider_disabled")
        return client

    async def _linked(self, identity: SocialIdentity) -> tuple[UUID, Home] | None:
        # Привязка живёт в доме аккаунта; какой это дом, знает только сама строка: читаем оба.
        found = await asyncio.gather(*(self._link_in(home, identity) for home in Home))
        for home, user_id in zip(Home, found, strict=True):
            if user_id is not None:
                await self._ensure_open(home, user_id)
                await self._touch(home, user_id, identity)
                return user_id, home
        return None

    async def _link_in(self, home: Home, identity: SocialIdentity) -> UUID | None:
        scope = TenancyScope(home)
        async with self._services.transactions.begin(scope, read_only=True) as session:
            return await session.scalar(
                select(UserIdentity.user_id).where(
                    UserIdentity.provider == identity.provider.value,
                    UserIdentity.subject == identity.subject,
                )
            )

    async def _touch(self, home: Home, user_id: UUID, identity: SocialIdentity) -> None:
        async with self._services.transactions.begin(TenancyScope(home, user_id)) as session:
            await session.execute(
                update(UserIdentity)
                .where(
                    UserIdentity.user_id == user_id,
                    UserIdentity.provider == identity.provider.value,
                )
                .values(last_used_at=func.now())
            )

    async def _by_proven_email(self, identity: SocialIdentity) -> tuple[UUID, Home] | None:
        if identity.email is None:
            return None
        try:
            address = normalize_email(identity.email)
        except InvalidEmailError:
            return None
        record = await self._services.directory.find_fresh(
            email_hmac(self._services.directory_key, address)
        )
        if record is None or record.state in NOT_ACCOUNTS:
            return None
        if record.state is not DirectoryState.ACTIVE:
            raise SocialRefusedError("account_unavailable")
        if not identity.email_verified:
            raise SocialRefusedError("social_link_requires_sign_in")
        await self._ensure_open(record.home, record.user_id)
        await self._link(record.home, record.user_id, identity)
        return record.user_id, record.home

    async def _link(self, home: Home, user_id: UUID, identity: SocialIdentity) -> None:
        # Новый subject того же провайдера у этого аккаунта заменяет прежний (урок черновика).
        async with self._services.transactions.begin(TenancyScope(home, user_id)) as session:
            await session.execute(
                insert(UserIdentity)
                .values(
                    id=new_id(), user_id=user_id, provider=identity.provider.value,
                    subject=identity.subject, email_verified_by_provider=identity.email_verified,
                )
                .on_conflict_do_update(
                    index_elements=[UserIdentity.user_id, UserIdentity.provider],
                    set_={"subject": identity.subject},
                )
            )  # fmt: skip
        log.info("Соцсеть привязана по подтверждённому адресу", provider=identity.provider.value)

    async def _ensure_open(self, home: Home, user_id: UUID) -> None:
        scope = TenancyScope(home, user_id)
        async with self._services.transactions.begin(scope, read_only=True) as session:
            state = await session.scalar(select(User.state).where(User.id == user_id))
        if state is None or sign_in_refusal(AccountState(state)) is not None:
            raise SocialRefusedError("account_unavailable")

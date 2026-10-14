"""Finishing social sign-in in the cabinet: a session ticket, or a new account by consent.

`complete` turns a session ticket into the browser's session. `register` creates the
account of a person a provider introduced, after they accepted the terms on the consent
screen: the same consents, the same directory claim and the same home by country as a
registration by address, with no password (a reset sets one later). An address the
provider did not prove (VK) gives an account whose address is not yet verified.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.i18n.locales import normalize_language
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.application import native_errors
from shosai.features.identity.application import registration_errors as errors
from shosai.features.identity.application.registration import ClientFacts
from shosai.features.identity.application.sessions import IssuedTokens, Sessions
from shosai.features.identity.contracts import AccountRegistered
from shosai.features.identity.domain.accounts import AccountState, sign_in_refusal
from shosai.features.identity.domain.directory import email_hmac
from shosai.features.identity.domain.emails import InvalidEmailError, normalize_email
from shosai.features.identity.domain.homes import CountryCode, InvalidCountryError, home_for_country
from shosai.features.identity.domain.registration import (
    CONSENT_VERSION,
    ConsentKind,
    RegistrationConsents,
)
from shosai.features.identity.domain.sessions import ClientKind
from shosai.features.identity.domain.social import SocialIdentity
from shosai.features.identity.infrastructure.directory import ClaimOutcome, Directory
from shosai.features.identity.infrastructure.records import User, UserConsent, UserIdentity
from shosai.features.identity.infrastructure.session_records import LoginEvent
from shosai.features.identity.infrastructure.social.consent_tickets import (
    CONSENT_LIFETIME,
    ConsentTickets,
)
from shosai.features.identity.infrastructure.social.flows import SocialStates

NAME_LENGTH = 80


@dataclass(frozen=True, slots=True)
class SocialRegistration:
    """The consent screen's answer."""

    ticket: str
    country: str
    language: str
    consents: RegistrationConsents


@dataclass(frozen=True, slots=True)
class SocialAccountServices:
    """What finishing social sign-in works with."""

    transactions: HomeTransactions
    directory: Directory
    states: SocialStates
    consent: ConsentTickets
    sessions: Sessions
    outbox: EventOutbox
    directory_key: bytes


class SocialAccounts:
    """Sessions and accounts out of social sign-in."""

    def __init__(self, services: SocialAccountServices) -> None:
        self._services = services

    async def complete(self, ticket: str, client: ClientFacts) -> tuple[IssuedTokens, str]:
        """The session of a known person, once per ticket, and where to return."""
        found = await self._services.states.take_ticket(ticket)
        if found is None:
            raise AppError("social_state_invalid", HTTPStatus.UNAUTHORIZED)
        scope = TenancyScope(found.home, found.user_id)
        async with self._services.transactions.begin(scope) as session:
            user = await session.get(User, found.user_id, with_for_update=True)
            if user is None:
                raise AppError("social_state_invalid", HTTPStatus.UNAUTHORIZED)
            refusal = sign_in_refusal(AccountState(user.state))
            if refusal is not None:
                raise native_errors.refused(refusal)
            user.last_login_at = datetime.now(UTC)
            session.add(_login(user.id, client))
            tokens = await self._services.sessions.open(
                session, user, found.home, ClientKind.WEB, client
            )
        return tokens, found.next_path

    async def register(self, form: SocialRegistration, client: ClientFacts) -> IssuedTokens:
        """A new account for a person a provider introduced, signed in at once."""
        services = self._services
        claim = services.consent.open(form.ticket)
        if claim is None or claim.identity.email is None:
            raise AppError("social_state_invalid", HTTPStatus.BAD_REQUEST)
        home, language = _checked(form)
        try:
            address = normalize_email(claim.identity.email)
        except InvalidEmailError as error:
            raise errors.invalid("invalid_email") from error
        if not await services.states.spend(form.ticket, CONSENT_LIFETIME):
            raise AppError("social_state_invalid", HTTPStatus.BAD_REQUEST)
        address_hmac = email_hmac(services.directory_key, address)
        user_id = new_id()
        if await services.directory.claim(address_hmac, user_id, home) is ClaimOutcome.TAKEN:
            raise errors.email_registered()
        async with services.transactions.begin(TenancyScope(home, user_id)) as session:
            user = _new_user(user_id, address.value, claim.identity, form.country, language)
            session.add(user)
            await session.flush()
            for consent in _consents(user_id, form.consents, client):
                session.add(consent)
            session.add(_identity(user_id, claim.identity))
            session.add(_login(user_id, client))
            await services.outbox.add(session, AccountRegistered(user_id=user_id))
            tokens = await services.sessions.open(session, user, home, ClientKind.WEB, client)
        await services.directory.activate(address_hmac, user_id)
        return tokens


def _checked(form: SocialRegistration) -> tuple[Home, str]:
    try:
        home = home_for_country(CountryCode(form.country))
    except InvalidCountryError as error:
        raise errors.invalid("invalid_country") from error
    problem = form.consents.problem(home)
    if problem is not None:
        raise errors.invalid(problem.value)
    language = normalize_language(form.language)
    if language is None:
        raise errors.invalid("unsupported_language")
    return home, language


def _new_user(
    user_id: UUID, email: str, identity: SocialIdentity, country: str, language: str
) -> User:
    name = (identity.display_name or email.partition("@")[0])[:NAME_LENGTH]
    verified_at = datetime.now(UTC) if identity.email_verified else None
    return User(
        id=user_id, email=email, password_hash=None, full_name=name, country=country,
        language=language, email_verified_at=verified_at,
    )  # fmt: skip


def _consents(
    user_id: UUID, consents: RegistrationConsents, client: ClientFacts
) -> list[UserConsent]:
    given = {
        ConsentKind.PERSONAL_DATA: consents.personal_data,
        ConsentKind.CROSS_BORDER: consents.cross_border,
        ConsentKind.MARKETING: consents.marketing,
    }
    return [
        UserConsent(
            id=new_id(),
            user_id=user_id,
            kind=kind.value,
            granted=value,
            version=CONSENT_VERSION,
            source="registration",
            ip=client.ip,
            user_agent=client.user_agent,
        )
        for kind, value in given.items()
    ]


def _identity(user_id: UUID, identity: SocialIdentity) -> UserIdentity:
    return UserIdentity(
        id=new_id(), user_id=user_id, provider=identity.provider.value,
        subject=identity.subject, email_verified_by_provider=identity.email_verified,
    )  # fmt: skip


def _login(user_id: UUID, client: ClientFacts) -> LoginEvent:
    return LoginEvent(
        id=new_id(), user_id=user_id, outcome="success", client_kind=ClientKind.WEB.value,
        ip=client.ip, user_agent=client.user_agent,
    )  # fmt: skip

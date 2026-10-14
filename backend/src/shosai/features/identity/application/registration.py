"""Starting a registration and resending its code (ADR 0045 point 3; identity plan §3.6).

The answer never tells whether an address is taken: a taken address gets the same 202, a
decoy id and the same time spent hashing, and its owner gets a warning by mail instead
of a code. A new registration is a row in the home of the country the person chose, with
its code mailed in the same transaction; Valkey learns only the route to that row.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
from typing import Final
from uuid import UUID

from shosai.core.db.transactions import HomeTransactions
from shosai.core.email.messages import EmailKind, OutgoingEmail
from shosai.core.email.port import EmailPort
from shosai.core.i18n.locales import normalize_language
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.features.identity.application import registration_errors as errors
from shosai.features.identity.application.routing import route_of, route_registration
from shosai.features.identity.domain.directory import email_hmac
from shosai.features.identity.domain.emails import (
    InvalidEmailError,
    NormalizedEmail,
    normalize_email,
)
from shosai.features.identity.domain.homes import CountryCode, InvalidCountryError, home_for_country
from shosai.features.identity.domain.passwords import new_password_problem
from shosai.features.identity.domain.registration import (
    MAX_RESENDS,
    PENDING_LIFETIME,
    RESEND_INTERVAL,
    DirectoryState,
    RegistrationConsents,
    code_hash,
    new_code,
)
from shosai.features.identity.emails.registration_attempt import REGISTRATION_ATTEMPT_KEY
from shosai.features.identity.emails.registration_code import REGISTRATION_CODE_KEY
from shosai.features.identity.infrastructure.captcha import Captcha
from shosai.features.identity.infrastructure.directory import Directory
from shosai.features.identity.infrastructure.password_hasher import PasswordHasher
from shosai.features.identity.infrastructure.records import PendingRegistration
from shosai.features.identity.infrastructure.registration_routes import RegistrationRoutes

# Не больше трёх регистраций одного адреса в час: защита чужого ящика от потока писем.
PER_ADDRESS: Final = RateLimit("identity.register_address", 3, timedelta(hours=1), 3)
# Владельцу занятого адреса предупреждение не шлём, если вход в аккаунт закрыт навсегда.
SILENT_STATES: Final = frozenset({DirectoryState.BANNED, DirectoryState.DELETED})


@dataclass(frozen=True, slots=True)
class ClientFacts:
    """Who sent the request, for the consent journal, the sign-in log and the captcha."""

    address: str
    user_agent: str | None

    @property
    def ip(self) -> str | None:
        """The address when it is an IP address; None for a client without one."""
        try:
            return str(ip_address(self.address))
        except ValueError:
            return None


@dataclass(frozen=True, slots=True)
class RegistrationForm:
    """The registration form, as the person filled it."""

    email: str
    password: str
    full_name: str
    country: str
    language: str
    consents: RegistrationConsents
    captcha_token: str | None


@dataclass(frozen=True, slots=True)
class RegistrationStarted:
    """The id the browser keeps to confirm the code, and when it may ask for another."""

    registration_id: UUID
    resend_after: timedelta


@dataclass(frozen=True, slots=True)
class RegistrationServices:
    """What registration works with, built once per process."""

    transactions: HomeTransactions
    directory: Directory
    routes: RegistrationRoutes
    hasher: PasswordHasher
    email: EmailPort
    captcha: Captcha
    limiter: RateLimiter
    directory_key: bytes


class Registration:
    """Start a registration; resend its code."""

    def __init__(self, services: RegistrationServices) -> None:
        self._services = services

    async def start(self, form: RegistrationForm, client: ClientFacts) -> RegistrationStarted:
        """Check the form, then mail a code to a free address or a warning to a taken one."""
        services = self._services
        if not await services.captcha.passed(form.captcha_token, client.address):
            raise errors.captcha_failed()
        email, home, language = _checked(form)
        address_hmac = email_hmac(services.directory_key, email)
        decision = await services.limiter.check(PER_ADDRESS, address_hmac.hex())
        if not decision.allowed:
            raise errors.resend_refused(
                "too_many_registrations", int(decision.retry_after.total_seconds()) + 1
            )
        holder = await services.directory.find_fresh(address_hmac)
        # Хеш считается и для занятого адреса: время ответа его не выдаёт.
        password_hash = await services.hasher.hash(form.password)
        registration_id = new_id()
        if holder is not None:
            if holder.state not in SILENT_STATES:
                await self._warn_owner(email.value, holder.home, holder.user_id, language)
            return RegistrationStarted(registration_id, RESEND_INTERVAL)
        code = new_code()
        await route_registration(services.routes, registration_id, address_hmac, home)
        now = datetime.now(UTC)
        async with services.transactions.begin(TenancyScope(home)) as session:
            session.add(
                PendingRegistration(
                    id=registration_id, email=email.value, email_hmac=address_hmac,
                    password_hash=password_hash, full_name=form.full_name.strip(),
                    country=form.country, language=language,
                    consent_cross_border=form.consents.cross_border,
                    consent_marketing=form.consents.marketing, consent_ip=client.ip,
                    consent_user_agent=client.user_agent,
                    code_hash=code_hash(registration_id, code),
                    last_sent_at=now, expires_at=now + PENDING_LIFETIME,
                )
            )  # fmt: skip
            await services.email.enqueue(session, _code_email(email.value, language, code))
        return RegistrationStarted(registration_id, RESEND_INTERVAL)

    async def resend(self, registration_id: UUID) -> RegistrationStarted:
        """A new code for a live registration: three at most, a minute apart."""
        services = self._services
        route = await route_of(services.routes, registration_id)
        if route is None:
            raise errors.invalid_code()
        home, address_hmac = route
        now = datetime.now(UTC)
        async with services.transactions.begin(TenancyScope(home)) as session:
            pending = await session.get(PendingRegistration, registration_id, with_for_update=True)
            if pending is None or pending.expires_at <= now:
                raise errors.invalid_code()
            if pending.resends >= MAX_RESENDS:
                raise errors.resend_refused(
                    "too_many_resends", int(PENDING_LIFETIME.total_seconds())
                )
            wait = pending.last_sent_at + RESEND_INTERVAL - now
            if wait > timedelta(0):
                raise errors.resend_refused("resend_too_soon", int(wait.total_seconds()) + 1)
            code = new_code()
            pending.code_hash = code_hash(registration_id, code)
            pending.resends += 1
            pending.last_sent_at = now
            pending.expires_at = now + PENDING_LIFETIME
            await services.email.enqueue(
                session, _code_email(pending.email, pending.language, code)
            )
        await route_registration(services.routes, registration_id, address_hmac, home)
        return RegistrationStarted(registration_id, RESEND_INTERVAL)

    async def _warn_owner(self, address: str, home: Home, user_id: UUID, language: str) -> None:
        # Письмо пишется в доме аккаунта: адрес и так там, через границу ничего не идёт.
        async with self._services.transactions.begin(TenancyScope(home, user_id)) as session:
            await self._services.email.enqueue(
                session,
                OutgoingEmail(
                    recipient=address, kind=EmailKind.ACCOUNT,
                    template=REGISTRATION_ATTEMPT_KEY, locale=language, user_id=user_id,
                ),
            )  # fmt: skip


def _checked(form: RegistrationForm) -> tuple[NormalizedEmail, Home, str]:
    try:
        email = normalize_email(form.email)
        country = CountryCode(form.country)
    except InvalidEmailError as error:
        raise errors.invalid("invalid_email") from error
    except InvalidCountryError as error:
        raise errors.invalid("invalid_country") from error
    problem = new_password_problem(form.password)
    if problem is not None:
        raise errors.invalid(problem.value)
    home = home_for_country(country)
    consent_problem = form.consents.problem(home)
    if consent_problem is not None:
        raise errors.invalid(consent_problem.value)
    language = normalize_language(form.language)
    if language is None:
        raise errors.invalid("unsupported_language")
    return email, home, language


def _code_email(address: str, language: str, code: str) -> OutgoingEmail:
    minutes = int(PENDING_LIFETIME.total_seconds() // 60)
    return OutgoingEmail(
        recipient=address, kind=EmailKind.ACCOUNT, template=REGISTRATION_CODE_KEY,
        locale=language, params={"minutes": minutes}, secrets={"code": code},
    )  # fmt: skip

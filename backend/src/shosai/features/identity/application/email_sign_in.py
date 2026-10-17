"""Sign-in by an emailed code (ADR 0048): one path for a known person and a new one.

`start` mails a 6-digit code and returns the sealed challenge; the answer is the same
whether or not the address has an account. The mail is written in the account's home, or —
for an address without one — in the home of the visitor (Russia, an unknown country or a
Russian interface: the Russian home), before the person names their country. `verify`
signs a known person in, or hands a new one a consent ticket that the consent screen turns
into an account in the home of the country they confirm.
"""

from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

from shosai.core.db.transactions import HomeTransactions
from shosai.core.email.messages import EmailKind, OutgoingEmail
from shosai.core.email.port import EmailPort
from shosai.core.i18n.locales import normalize_language
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.features.identity.application import native_errors
from shosai.features.identity.application import registration_errors as errors
from shosai.features.identity.application.registration import ClientFacts
from shosai.features.identity.application.sessions import IssuedTokens, Sessions
from shosai.features.identity.domain.accounts import AccountState, sign_in_refusal
from shosai.features.identity.domain.directory import email_hmac
from shosai.features.identity.domain.email_codes import (
    CHALLENGE_LIFETIME,
    MAX_ATTEMPTS,
    challenge_code_hash,
    challenge_code_matches,
    new_nonce,
)
from shosai.features.identity.domain.emails import InvalidEmailError, is_disposable, normalize_email
from shosai.features.identity.domain.homes import home_for_visitor
from shosai.features.identity.domain.registration import (
    MAX_RESENDS,
    NOT_ACCOUNTS,
    RESEND_INTERVAL,
    DirectoryState,
    new_code,
)
from shosai.features.identity.domain.sessions import ClientKind
from shosai.features.identity.emails.sign_in_code import SIGN_IN_CODE_KEY
from shosai.features.identity.infrastructure.captcha import Captcha
from shosai.features.identity.infrastructure.directory import Directory, DirectoryRecord
from shosai.features.identity.infrastructure.email_challenges import (
    ChallengeClaim,
    ChallengeSeals,
    ChallengeStates,
    ChallengesUnavailableError,
)
from shosai.features.identity.infrastructure.records import User
from shosai.features.identity.infrastructure.session_records import LoginEvent
from shosai.features.identity.infrastructure.sign_in_failures import SignInFailures
from shosai.features.identity.infrastructure.social.consent_tickets import (
    ConsentClaim,
    ConsentTickets,
)

# Не больше пяти кодов на адрес в час: защита чужого ящика от потока писем.
PER_ADDRESS: Final = RateLimit("identity.email_code_address", 5, timedelta(hours=1), 5)
# Закрытому навсегда аккаунту код не шлём; ответ тот же, что всем.
SILENT_STATES: Final = frozenset({DirectoryState.BANNED})
RENEWAL_REFUSALS: Final = {-2: "too_many_resends", -3: "resend_too_soon"}


@dataclass(frozen=True, slots=True)
class EmailStart:
    """The address a person typed, and what the request says about them."""

    email: str
    language: str
    next_path: str
    captcha_token: str | None
    # Страна посетителя от edge (GeoIP); от клиента страна не принимается.
    country: str | None


@dataclass(frozen=True, slots=True)
class ChallengeStarted:
    """The sealed challenge the browser keeps, and when it may ask for another code."""

    challenge: str
    resend_after: timedelta


@dataclass(frozen=True, slots=True)
class EmailVerified:
    """A session for a known person, or a consent ticket for a new one."""

    tokens: IssuedTokens | None
    consent_ticket: str | None
    next_path: str


@dataclass(frozen=True, slots=True)
class EmailSignInServices:
    """What sign-in by code works with, built once per process."""

    transactions: HomeTransactions
    directory: Directory
    seals: ChallengeSeals
    states: ChallengeStates
    consent: ConsentTickets
    captcha: Captcha
    failures: SignInFailures
    limiter: RateLimiter
    email: EmailPort
    sessions: Sessions
    directory_key: bytes


class EmailSignIn:
    """Start, resend and verify sign-in by an emailed code."""

    def __init__(self, services: EmailSignInServices) -> None:
        self._services = services

    async def start(self, form: EmailStart, client: ClientFacts) -> ChallengeStarted:
        """Mail a code to the address and return the sealed challenge."""
        services = self._services
        try:
            address = normalize_email(form.email)
        except InvalidEmailError as error:
            raise errors.invalid("invalid_email") from error
        language = normalize_language(form.language)
        if language is None:
            raise errors.invalid("unsupported_language")
        address_hmac = email_hmac(services.directory_key, address)
        if await services.failures.captcha_due(client.address, address_hmac) and not (
            await services.captcha.passed(form.captcha_token, client.address)
        ):
            raise errors.captcha_failed()
        decision = await services.limiter.check(PER_ADDRESS, address_hmac.hex())
        if not decision.allowed:
            seconds = int(decision.retry_after.total_seconds()) + 1
            raise errors.resend_refused("too_many_codes", seconds)
        account = _account(await services.directory.find_fresh(address_hmac))
        home = account.home if account else home_for_visitor(form.country, language)
        nonce = new_nonce()
        claim = ChallengeClaim(nonce, address.value, home, form.next_path, language)
        if account is not None and account.state in SILENT_STATES:
            return ChallengeStarted(services.seals.seal(claim), RESEND_INTERVAL)
        code = new_code()
        await self._guarded(services.states.create(nonce, challenge_code_hash(nonce, code)))
        await self._mail(claim, code, account.user_id if account else None)
        return ChallengeStarted(services.seals.seal(claim), RESEND_INTERVAL)

    async def resend(self, challenge: str) -> ChallengeStarted:
        """A new code for a live challenge, at the registration's pace."""
        services = self._services
        claim = services.seals.open(challenge)
        if claim is None:
            raise errors.invalid_code()
        code = new_code()
        pacing = (int(RESEND_INTERVAL.total_seconds()), MAX_RESENDS)
        renewal = await self._guarded(
            services.states.renew(claim.nonce, challenge_code_hash(claim.nonce, code), pacing)
        )
        if renewal.outcome == -1:
            raise errors.invalid_code()
        if renewal.outcome in RENEWAL_REFUSALS:
            wait = renewal.wait_seconds or int(CHALLENGE_LIFETIME.total_seconds())
            raise errors.resend_refused(RENEWAL_REFUSALS[renewal.outcome], wait)
        address_hmac = email_hmac(services.directory_key, normalize_email(claim.email))
        account = _account(await services.directory.find(address_hmac))
        await self._mail(claim, code, account.user_id if account else None)
        return ChallengeStarted(challenge, RESEND_INTERVAL)

    async def verify(self, challenge: str, code: str, client: ClientFacts) -> EmailVerified:
        """Sign a known person in, or give a new one a consent ticket."""
        services = self._services
        claim = services.seals.open(challenge)
        if claim is None:
            raise errors.invalid_code()
        found = await self._guarded(services.states.attempt(claim.nonce))
        if found is None:
            raise errors.invalid_code()
        stored, attempts = found
        address_hmac = email_hmac(services.directory_key, normalize_email(claim.email))
        if attempts > MAX_ATTEMPTS:
            await self._guarded(services.states.end(claim.nonce))
            raise errors.code_locked()
        if not challenge_code_matches(claim.nonce, code, stored):
            await services.failures.failed(client.address, address_hmac)
            if attempts == MAX_ATTEMPTS:
                await self._guarded(services.states.end(claim.nonce))
                raise errors.code_locked()
            raise errors.invalid_code()
        # Код верен, но засчитывается один раз: параллельный запрос с тем же кодом опоздал.
        if not await self._guarded(services.states.end(claim.nonce)):
            raise errors.invalid_code()
        account = _account(await services.directory.find(address_hmac))
        if account is None:
            # Новый аккаунт на одноразовом адресе не создаётся; вошедшим раньше это не мешает.
            if is_disposable(normalize_email(claim.email)):
                raise errors.disposable_domain()
            consent = ConsentClaim(None, claim.next_path, claim.language, claim.email)
            return EmailVerified(None, services.consent.seal(consent), claim.next_path)
        tokens = await self._signed_in(account, client)
        await services.failures.succeeded(address_hmac)
        return EmailVerified(tokens, None, claim.next_path)

    async def _signed_in(self, account: DirectoryRecord, client: ClientFacts) -> IssuedTokens:
        services = self._services
        scope = TenancyScope(account.home, account.user_id)
        async with services.transactions.begin(scope) as session:
            user = await session.get(User, account.user_id, with_for_update=True)
            if user is None:
                raise errors.invalid_code()
            refusal = sign_in_refusal(AccountState(user.state))
            if refusal is not None:
                raise native_errors.refused(refusal)
            now = datetime.now(UTC)
            user.last_login_at = now
            # Код из письма доказывает, что адрес принадлежит человеку.
            if user.email_verified_at is None:
                user.email_verified_at = now
            session.add(_login(user.id, client))
            return await services.sessions.open(session, user, account.home, ClientKind.WEB, client)

    async def _mail(self, claim: ChallengeClaim, code: str, user_id: UUID | None) -> None:
        mail = OutgoingEmail(
            recipient=claim.email, kind=EmailKind.ACCOUNT, template=SIGN_IN_CODE_KEY,
            locale=claim.language, user_id=user_id,
            params={"minutes": int(CHALLENGE_LIFETIME.total_seconds() // 60)},
            secrets={"code": code},
        )  # fmt: skip
        async with self._services.transactions.begin(TenancyScope(claim.home, user_id)) as session:
            await self._services.email.enqueue(session, mail)

    @staticmethod
    async def _guarded[T](call: Awaitable[T]) -> T:
        try:
            return await call
        except ChallengesUnavailableError as error:
            raise errors.sign_in_unavailable() from error


def _account(record: DirectoryRecord | None) -> DirectoryRecord | None:
    # Строка каталога без аккаунта (заявка или стёртый) — адрес ещё свободен.
    return None if record is None or record.state in NOT_ACCOUNTS else record


def _login(user_id: UUID, client: ClientFacts) -> LoginEvent:
    return LoginEvent(
        id=new_id(), user_id=user_id, outcome="success", client_kind=ClientKind.WEB.value,
        ip=client.ip, user_agent=client.user_agent,
    )  # fmt: skip

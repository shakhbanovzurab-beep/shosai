"""Signing in with an address and a password (§11 flow 4; ADR 0045 points 1, 4).

The directory names the home (cached, the last copy during an EU outage), the account is
read there, the password is checked outside any transaction, and the session is written
in one transaction with the sign-in log and the last sign-in time. An unknown address
spends a decoy check and answers like a wrong password. The exact reason a correct
password does not open an account (banned, frozen, disabled) is told only after the
password proved the person (draft commit 7088cc3b4).
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.application import native_errors
from shosai.features.identity.application.registration import ClientFacts
from shosai.features.identity.application.sessions import IssuedTokens, Sessions
from shosai.features.identity.domain.accounts import AccountState, sign_in_refusal
from shosai.features.identity.domain.directory import email_hmac
from shosai.features.identity.domain.emails import InvalidEmailError, normalize_email
from shosai.features.identity.domain.registration import NOT_ACCOUNTS
from shosai.features.identity.domain.sessions import ClientKind
from shosai.features.identity.infrastructure.captcha import Captcha
from shosai.features.identity.infrastructure.directory import Directory, DirectoryRecord
from shosai.features.identity.infrastructure.password_hasher import PasswordHasher
from shosai.features.identity.infrastructure.records import PendingRegistration, User
from shosai.features.identity.infrastructure.registration_routes import (
    RegistrationRoutes,
    RegistrationRoutesUnavailableError,
)
from shosai.features.identity.infrastructure.session_records import LoginEvent
from shosai.features.identity.infrastructure.sign_in_failures import SignInFailures

# Сколько живых регистраций адреса проверять паролем: больше — признак перебора.
PENDING_CHECKED = 3


@dataclass(frozen=True, slots=True)
class SignInAttempt:
    """What the client sent and where from."""

    email: str
    password: str
    captcha_token: str | None
    kind: ClientKind
    client: ClientFacts


@dataclass(frozen=True, slots=True)
class SignInServices:
    """What sign-in works with."""

    transactions: HomeTransactions
    directory: Directory
    routes: RegistrationRoutes
    hasher: PasswordHasher
    captcha: Captcha
    failures: SignInFailures
    sessions: Sessions
    directory_key: bytes


class SignIn:
    """Sign a person in and open a refresh family for the client."""

    def __init__(self, services: SignInServices) -> None:
        self._services = services

    async def sign_in(self, attempt: SignInAttempt) -> IssuedTokens:
        """The session of a correct password, or the draft's 400, 401 or 403."""
        services = self._services
        try:
            email = normalize_email(attempt.email)
        except InvalidEmailError as error:
            await services.hasher.verify(attempt.password, None)
            raise native_errors.unauthorized("invalid_credentials") from error
        address_hmac = email_hmac(services.directory_key, email)
        address = attempt.client.address
        if await services.failures.captcha_due(address, address_hmac) and not (
            await services.captcha.passed(attempt.captcha_token, address)
        ):
            raise native_errors.captcha_failed()
        record = await services.directory.find(address_hmac)
        user = await self._account(record)
        if user is None or record is None:
            await services.hasher.verify(attempt.password, None)
            await services.failures.failed(address, address_hmac)
            if await self._pending_password(address_hmac, attempt.password):
                raise native_errors.email_not_verified()
            raise native_errors.unauthorized("invalid_credentials")
        if not await services.hasher.verify(attempt.password, user.password_hash):
            await services.failures.failed(address, address_hmac)
            await self._log(record.home, user.id, "wrong_password", attempt)
            raise native_errors.unauthorized("invalid_credentials")
        refusal = sign_in_refusal(AccountState(user.state))
        if refusal is not None:
            await self._log(record.home, user.id, "blocked", attempt)
            raise native_errors.refused(refusal)
        async with services.transactions.begin(TenancyScope(record.home, user.id)) as session:
            account = await session.get(User, user.id, with_for_update=True)
            if account is None:
                raise native_errors.unauthorized("invalid_credentials")
            account.last_login_at = datetime.now(UTC)
            self._add_log(session, account.id, "success", attempt)
            tokens = await services.sessions.open(
                session, account, record.home, attempt.kind, attempt.client
            )
        await services.failures.succeeded(address_hmac)
        return tokens

    async def _account(self, record: DirectoryRecord | None) -> User | None:
        # Заявка без записанного аккаунта — ещё не аккаунт, стёртый — уже не аккаунт.
        if record is None or record.state in NOT_ACCOUNTS:
            return None
        scope = TenancyScope(record.home, record.user_id)
        async with self._services.transactions.begin(scope, read_only=True) as session:
            return await session.get(User, record.user_id)

    async def _pending_password(self, address_hmac: bytes, password: str) -> bool:
        """Whether the password is a live registration's of the address (draft behaviour)."""
        routes = self._services.routes
        try:
            pending = (await routes.pending(address_hmac))[:PENDING_CHECKED]
            homes = [await routes.route(registration_id) for registration_id in pending]
        except RegistrationRoutesUnavailableError:
            return False
        for registration_id, route in zip(pending, homes, strict=True):
            if route is not None and await self._matches(route[0], registration_id, password):
                return True
        return False

    async def _matches(self, home: Home, registration_id: UUID, password: str) -> bool:
        async with self._services.transactions.begin(TenancyScope(home), read_only=True) as session:
            pending = await session.get(PendingRegistration, registration_id)
        if pending is None or pending.expires_at <= datetime.now(UTC):
            return False
        return await self._services.hasher.verify(password, pending.password_hash)

    async def _log(self, home: Home, user_id: UUID, outcome: str, attempt: SignInAttempt) -> None:
        async with self._services.transactions.begin(TenancyScope(home, user_id)) as session:
            self._add_log(session, user_id, outcome, attempt)

    @staticmethod
    def _add_log(
        session: AsyncSession, user_id: UUID, outcome: str, attempt: SignInAttempt
    ) -> None:
        session.add(
            LoginEvent(
                id=new_id(), user_id=user_id, outcome=outcome, client_kind=attempt.kind.value,
                ip=attempt.client.ip, user_agent=attempt.client.user_agent,
            )
        )  # fmt: skip

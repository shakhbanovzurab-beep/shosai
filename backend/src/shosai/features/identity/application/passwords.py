"""Forgotten, reset and changed passwords (ADR 0045; draft spec 001).

"Forgot" always answers the same and mails a link only to an active account; a new link
deletes the older ones. A reset uses its link once, by one conditional update, and a
reset or a change ends every session of the account: the token version goes up, every
family is revoked, and the account marker in Valkey makes live access tokens fail on their
next request. A change keeps the person signed in on the device that made it, with a new
family; an account with no password (social sign-in only) sets one by reset.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Final

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.email.messages import EmailKind, OutgoingEmail
from shosai.core.email.port import EmailPort
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.features.identity.application import registration_errors as errors
from shosai.features.identity.application.registration import ClientFacts
from shosai.features.identity.application.sessions import IssuedTokens, Sessions
from shosai.features.identity.contracts import Principal, SessionsRevoked
from shosai.features.identity.domain.accounts import AccountState
from shosai.features.identity.domain.directory import email_hmac
from shosai.features.identity.domain.emails import InvalidEmailError, normalize_email
from shosai.features.identity.domain.password_reset import (
    RESET_LIFETIME,
    new_reset_token,
    parse_reset_token,
)
from shosai.features.identity.domain.passwords import new_password_problem
from shosai.features.identity.domain.registration import DirectoryState
from shosai.features.identity.domain.sessions import ClientKind
from shosai.features.identity.emails.password_reset import RESET_LINK_MAIL_KEY
from shosai.features.identity.infrastructure.account_markers import AccountMarker, AccountMarkers
from shosai.features.identity.infrastructure.captcha import Captcha
from shosai.features.identity.infrastructure.directory import Directory
from shosai.features.identity.infrastructure.password_hasher import PasswordHasher
from shosai.features.identity.infrastructure.records import User
from shosai.features.identity.infrastructure.session_records import (
    PasswordResetToken,
    RefreshSession,
)

PER_ADDRESS: Final = RateLimit("identity.password_forgot_address", 3, timedelta(hours=1), 3)


@dataclass(frozen=True, slots=True)
class PasswordServices:
    """What the password routes work with."""

    transactions: HomeTransactions
    directory: Directory
    hasher: PasswordHasher
    email: EmailPort
    captcha: Captcha
    limiter: RateLimiter
    markers: AccountMarkers
    outbox: EventOutbox
    sessions: Sessions
    directory_key: bytes
    reset_page: str


class Passwords:
    """Mail a reset link; reset by it; change a password with the current one."""

    def __init__(self, services: PasswordServices) -> None:
        self._services = services

    async def forgot(self, email: str, captcha_token: str | None, client: ClientFacts) -> None:
        """Mail a reset link to an active account; the same silence for anything else."""
        services = self._services
        if not await services.captcha.passed(captcha_token, client.address):
            raise errors.captcha_failed()
        try:
            address = normalize_email(email)
        except InvalidEmailError:
            return
        address_hmac = email_hmac(services.directory_key, address)
        if not (await services.limiter.check(PER_ADDRESS, address_hmac.hex())).allowed:
            return
        record = await services.directory.find(address_hmac)
        if record is None or record.state is not DirectoryState.ACTIVE:
            return
        token = new_reset_token(record.home)
        scope = TenancyScope(record.home, record.user_id)
        async with services.transactions.begin(scope) as session:
            user = await session.get(User, record.user_id)
            if user is None or user.state != AccountState.ACTIVE.value:
                return
            await session.execute(
                delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
            )
            session.add(
                PasswordResetToken(
                    token_hash=token.digest, user_id=user.id,
                    expires_at=datetime.now(UTC) + RESET_LIFETIME,
                )
            )  # fmt: skip
            await services.email.enqueue(
                session,
                OutgoingEmail(
                    recipient=user.email, kind=EmailKind.ACCOUNT, template=RESET_LINK_MAIL_KEY,
                    locale=user.language, user_id=user.id,
                    params={"minutes": int(RESET_LIFETIME.total_seconds() // 60)},
                    secrets={"link": f"{services.reset_page}?token={token.text}"},
                ),
            )  # fmt: skip

    async def reset(self, token_text: str, new_password: str) -> None:
        """Set the password of a link's account once; every session of the account ends."""
        services = self._services
        token = parse_reset_token(token_text)
        if token is None:
            raise invalid_token()
        _check_new(new_password)
        password_hash = await services.hasher.hash(new_password)
        async with services.transactions.begin(TenancyScope(token.home)) as session:
            user_id = await session.scalar(
                update(PasswordResetToken)
                .where(
                    PasswordResetToken.token_hash == token.digest,
                    PasswordResetToken.used_at.is_(None),
                    PasswordResetToken.expires_at > datetime.now(UTC),
                )
                .values(used_at=datetime.now(UTC))
                .returning(PasswordResetToken.user_id)
            )
            user = (
                None if user_id is None else await session.get(User, user_id, with_for_update=True)
            )
            if user is not None:
                user.password_hash = password_hash
                await self._end_sessions(session, user, "password_reset")
        if user is None:
            raise invalid_token()
        await self._mark(user)

    async def change(
        self, principal: Principal, current: str | None, new_password: str, client: ClientFacts
    ) -> IssuedTokens:
        """Change the password; every other session ends, this device gets a new one."""
        services = self._services
        _check_new(new_password)
        async with services.transactions.begin(principal.scope(), read_only=True) as session:
            stored = await session.get(User, principal.user_id)
        if stored is None:
            raise AppError("user_not_found", HTTPStatus.UNAUTHORIZED)
        if stored.password_hash is not None and not await services.hasher.verify(
            current or "", stored.password_hash
        ):
            raise AppError("wrong_password", HTTPStatus.FORBIDDEN)
        password_hash = await services.hasher.hash(new_password)
        async with services.transactions.begin(principal.scope()) as session:
            user = await session.get(User, principal.user_id, with_for_update=True)
            if user is None:
                raise AppError("user_not_found", HTTPStatus.UNAUTHORIZED)
            user.password_hash = password_hash
            await self._end_sessions(session, user, "password_change")
            tokens = await services.sessions.open(
                session, user, principal.home, ClientKind.WEB, client
            )
        await self._mark(user)
        return tokens

    async def _end_sessions(self, session: AsyncSession, user: User, reason: str) -> None:
        user.token_version += 1
        now = datetime.now(UTC)
        await session.execute(
            update(RefreshSession)
            .where(RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None))
            .values(revoked_at=now, revoke_reason=reason)
        )
        await session.execute(
            delete(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)
            )
        )
        await self._services.outbox.add(session, SessionsRevoked(user_id=user.id))

    async def _mark(self, user: User) -> None:
        marker = AccountMarker(user.token_version, AccountState(user.state))
        await self._services.markers.write(user.id, marker)


def invalid_token() -> AppError:
    """400 `invalid_token`: the link is unknown, used or expired."""
    return AppError("invalid_token", HTTPStatus.BAD_REQUEST)


def _check_new(password: str) -> None:
    problem = new_password_problem(password)
    if problem is not None:
        raise errors.invalid(problem.value)

"""Confirming a registration's code: the account is born (ADR 0045 point 3, §6).

Four short steps, none spanning two homes in one transaction (§4.1 rule 4), each safe to
repeat with the same registration id:

1. In the registration's home, check the code under a row lock. A wrong code is counted
   and committed. The first right one fixes the account id on the row.
2. In the EU home, claim the address in the directory. The first confirmed registration
   of an address wins. A later one gets 409, and its pending row is dropped.
3. In the home, write the account, its consents and `AccountRegistered`, and drop the
   pending row.
4. In the EU home, mark the claim active.

A crash between steps leaves a claim that a sweep finishes or releases (`sweeps.py`).
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.errors import HomeUnavailableError
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.application import registration_errors as errors
from shosai.features.identity.application.registration import ClientFacts, RegistrationServices
from shosai.features.identity.application.routing import route_of
from shosai.features.identity.application.sessions import IssuedTokens, Sessions
from shosai.features.identity.contracts import AccountRegistered
from shosai.features.identity.domain.registration import (
    CONSENT_VERSION,
    MAX_CODE_ATTEMPTS,
    ConsentKind,
    code_matches,
)
from shosai.features.identity.domain.sessions import ClientKind
from shosai.features.identity.infrastructure.directory import ClaimOutcome
from shosai.features.identity.infrastructure.records import (
    PendingRegistration,
    User,
    UserConsent,
)
from shosai.features.identity.infrastructure.registration_routes import (
    RegistrationRoutesUnavailableError,
)

log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Verified:
    """The account the confirmed registration created, signed in on the confirming client."""

    user_id: UUID
    home: Home
    tokens: IssuedTokens


class Verification:
    """Confirm a registration's code."""

    def __init__(
        self, services: RegistrationServices, outbox: EventOutbox, sessions: Sessions
    ) -> None:
        self._services = services
        self._outbox = outbox
        self._sessions = sessions

    async def confirm(self, registration_id: UUID, code: str, client: ClientFacts) -> Verified:
        """Create the account of a registration whose code is right."""
        route = await route_of(self._services.routes, registration_id)
        if route is None:
            raise errors.invalid_code()
        home, address_hmac = route
        user_id = await self._check_code(home, registration_id, code)
        outcome = await self._services.directory.claim(address_hmac, user_id, home)
        if outcome is ClaimOutcome.TAKEN:
            await self._drop(home, registration_id, address_hmac)
            raise errors.email_registered()
        async with self._services.transactions.begin(TenancyScope(home, user_id)) as session:
            user = await self._create_account(session, registration_id, user_id)
            tokens = await self._sessions.open(session, user, home, ClientKind.WEB, client)
        await self._settle(address_hmac, user_id, registration_id)
        return Verified(user_id, home, tokens)

    async def _check_code(self, home: Home, registration_id: UUID, code: str) -> UUID:
        refusal: Exception | None = None
        async with self._services.transactions.begin(TenancyScope(home)) as session:
            pending = await session.get(PendingRegistration, registration_id, with_for_update=True)
            if pending is None or pending.expires_at <= datetime.now(UTC):
                raise errors.invalid_code()
            if pending.attempts >= MAX_CODE_ATTEMPTS:
                raise errors.registration_locked()
            if code_matches(registration_id, code, pending.code_hash):
                pending.user_id = pending.user_id or new_id()
                return pending.user_id
            # Неверный код считается и фиксируется: ошибка — после коммита.
            pending.attempts += 1
            refusal = (
                errors.registration_locked()
                if pending.attempts >= MAX_CODE_ATTEMPTS
                else errors.invalid_code()
            )
        raise refusal

    async def _create_account(
        self, session: AsyncSession, registration_id: UUID, user_id: UUID
    ) -> User:
        pending = await session.get(PendingRegistration, registration_id, with_for_update=True)
        if pending is None:
            # Параллельное подтверждение уже записало аккаунт и открыло свою сессию.
            raise errors.invalid_code()
        now = datetime.now(UTC)
        user = User(
            id=user_id, email=pending.email, password_hash=pending.password_hash,
            full_name=pending.full_name, country=pending.country, language=pending.language,
            timezone=pending.timezone, email_verified_at=now,
        )  # fmt: skip
        session.add(user)
        await session.flush()
        granted = {
            ConsentKind.PERSONAL_DATA: True,
            ConsentKind.CROSS_BORDER: pending.consent_cross_border,
            ConsentKind.MARKETING: pending.consent_marketing,
        }
        for kind, value in granted.items():
            session.add(
                UserConsent(
                    id=new_id(), user_id=user_id, kind=kind.value, granted=value,
                    version=CONSENT_VERSION, source="registration", ip=pending.consent_ip,
                    user_agent=pending.consent_user_agent, recorded_at=pending.created_at,
                )
            )  # fmt: skip
        await session.delete(pending)
        await self._outbox.add(session, AccountRegistered(user_id=user_id))
        return user

    async def _settle(self, address_hmac: bytes, user_id: UUID, registration_id: UUID) -> None:
        # Аккаунт уже записан: сбой здесь не отменяет регистрацию, хвост доделает обход.
        try:
            await self._services.directory.activate(address_hmac, user_id)
        except HomeUnavailableError:
            log.warning("Каталог не принял активацию, её завершит обход", user_id=str(user_id))
        try:
            await self._services.routes.forget(registration_id, address_hmac)
        except RegistrationRoutesUnavailableError:
            log.warning("Маршрут регистрации не удалён, истечёт сам")

    async def _drop(self, home: Home, registration_id: UUID, address_hmac: bytes) -> None:
        async with self._services.transactions.begin(TenancyScope(home)) as session:
            await session.execute(
                delete(PendingRegistration).where(PendingRegistration.id == registration_id)
            )
        try:
            await self._services.routes.forget(registration_id, address_hmac)
        except RegistrationRoutesUnavailableError:
            log.warning("Маршрут регистрации не удалён, истечёт сам")

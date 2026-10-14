"""Where a pending registration lives, kept in Valkey (ADR 0045 point 3).

The registration itself — address, name, password hash, code — is a row in the home of
the country the person chose. Valkey, in the EU, keeps only what routes to that row: the
registration id, the address's HMAC and the home, with the registration's own lifetime.
Verification and resend find the home here; sign-in finds here whether an address has a
registration waiting. Without Valkey a registration cannot be started or confirmed (503);
nothing personal is ever written to it.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Final
from uuid import UUID

from redis.asyncio import Redis

from shosai.core.kernel.homes import Home
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.kv.keys import build_key

DEADLINE: Final = timedelta(milliseconds=200)
SEPARATOR: Final = ":"


class RegistrationRoutesUnavailableError(Exception):
    """Valkey did not answer in time; the registration step cannot proceed."""


# Маршрут и множество регистраций адреса пишутся и снимаются одним скриптом: атомарно.
RECORD: Final = """
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[3])
redis.call('SADD', KEYS[2], ARGV[2])
redis.call('EXPIRE', KEYS[2], ARGV[3])
return 1
"""
FORGET: Final = """
redis.call('DEL', KEYS[1])
redis.call('SREM', KEYS[2], ARGV[1])
return 1
"""


class RegistrationRoutes:
    """Registration id → (home, HMAC); HMAC → the ids of its live registrations."""

    def __init__(self, valkey: Redis) -> None:
        self._valkey = valkey

    async def record(
        self, registration_id: UUID, email_hmac: bytes, home: Home, lifetime: timedelta
    ) -> None:
        """Route a new registration, or extend a resent one, for its lifetime."""
        route = f"{home.value}{SEPARATOR}{email_hmac.hex()}"
        seconds = str(int(lifetime.total_seconds()))
        async with _deadline():
            await self._valkey.eval(
                RECORD,
                2,
                _route_key(registration_id),
                _pending_key(email_hmac),
                route,
                registration_id.hex,
                seconds,
            )

    async def route(self, registration_id: UUID) -> tuple[Home, bytes] | None:
        """The home and HMAC of a live registration, or None when it expired or never was."""
        async with _deadline():
            value = await self._valkey.get(_route_key(registration_id))
        if value is None:
            return None
        home, _, email_hmac = _text(value).partition(SEPARATOR)
        return Home(home), bytes.fromhex(email_hmac)

    async def pending(self, email_hmac: bytes) -> list[UUID]:
        """The live registrations of an address, for sign-in's `email_not_verified`."""
        async with _deadline():
            members = await self._valkey.smembers(_pending_key(email_hmac))
        return [UUID(hex=_text(member)) for member in members]

    async def forget(self, registration_id: UUID, email_hmac: bytes) -> None:
        """Drop the route of a finished registration."""
        async with _deadline():
            await self._valkey.eval(
                FORGET,
                2,
                _route_key(registration_id),
                _pending_key(email_hmac),
                registration_id.hex,
            )


@asynccontextmanager
async def _deadline() -> AsyncIterator[None]:
    """One Valkey call under its deadline; any failure is `RegistrationRoutesUnavailableError`."""
    try:
        async with asyncio.timeout(DEADLINE.total_seconds()):
            yield
    except REDIS_FAILURES as error:
        raise RegistrationRoutesUnavailableError from error


def _route_key(registration_id: UUID) -> str:
    return build_key("identity", "registration", registration_id.hex)


def _pending_key(email_hmac: bytes) -> str:
    return build_key("identity", "pending", email_hmac.hex())


def _text(value: bytes | str) -> str:
    return value.decode("ascii") if isinstance(value, bytes) else value

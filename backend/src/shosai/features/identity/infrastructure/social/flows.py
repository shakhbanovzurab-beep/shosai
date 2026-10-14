"""The short-lived state of social sign-in in Valkey: flows, session tickets, spent tickets.

A flow (10 minutes) keeps the provider, the PKCE verifier, where to return and the
language, keyed by the nonce the signed `state` carries; GETDEL takes it once, so a
replayed callback finds nothing. A session ticket (2 minutes) names the account and its
home for the cabinet's `complete`; GETDEL again. A consent ticket travels encrypted in
the URL instead (`consent_tickets.py`); here only its hash is marked spent. Nothing
personal is written: ids, a home, a path, a language code.
"""

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Final
from uuid import UUID

from redis.asyncio import Redis

from shosai.core.kernel.homes import Home
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.kv.keys import build_key
from shosai.features.identity.domain.social import Provider

FLOW_LIFETIME: Final = timedelta(minutes=10)
TICKET_LIFETIME: Final = timedelta(minutes=2)
DEADLINE: Final = timedelta(milliseconds=200)


class SocialStateUnavailableError(Exception):
    """Valkey did not answer: social sign-in cannot proceed now."""


@dataclass(frozen=True, slots=True)
class Flow:
    """One started sign-in at a provider."""

    provider: Provider
    verifier: str
    next_path: str
    language: str


@dataclass(frozen=True, slots=True)
class SessionTicket:
    """An account proven by a provider, waiting for the cabinet to open its session."""

    user_id: UUID
    home: Home
    next_path: str


class SocialStates:
    """Flows and tickets."""

    def __init__(self, valkey: Redis) -> None:
        self._valkey = valkey

    async def open_flow(self, nonce: str, flow: Flow) -> None:
        """Keep a flow under its nonce for 10 minutes."""
        value = json.dumps(
            {"provider": flow.provider.value, "verifier": flow.verifier,
             "next": flow.next_path, "language": flow.language}
        )  # fmt: skip
        await self._set(_key("social_flow", nonce), value, FLOW_LIFETIME)

    async def take_flow(self, nonce: str) -> Flow | None:
        """The flow of a nonce, once."""
        payload = await self._getdel(_key("social_flow", nonce))
        if payload is None:
            return None
        return Flow(
            Provider(payload["provider"]), payload["verifier"], payload["next"], payload["language"]
        )

    async def issue_ticket(self, ticket: str, session: SessionTicket) -> None:
        """Keep a session ticket for 2 minutes."""
        value = json.dumps(
            {"user_id": str(session.user_id), "home": session.home.value, "next": session.next_path}
        )
        await self._set(_key("social_ticket", _digest(ticket)), value, TICKET_LIFETIME)

    async def take_ticket(self, ticket: str) -> SessionTicket | None:
        """The session ticket, once."""
        payload = await self._getdel(_key("social_ticket", _digest(ticket)))
        if payload is None:
            return None
        return SessionTicket(UUID(payload["user_id"]), Home(payload["home"]), payload["next"])

    async def spend(self, ticket: str, lifetime: timedelta) -> bool:
        """Mark a consent ticket used; False when it was used before."""
        try:
            async with asyncio.timeout(DEADLINE.total_seconds()):
                first = await self._valkey.set(
                    _key("social_spent", _digest(ticket)),
                    "1",
                    nx=True,
                    ex=int(lifetime.total_seconds()),
                )
        except REDIS_FAILURES as error:
            raise SocialStateUnavailableError from error
        return bool(first)

    async def _set(self, key: str, value: str, lifetime: timedelta) -> None:
        try:
            async with asyncio.timeout(DEADLINE.total_seconds()):
                await self._valkey.set(key, value, ex=int(lifetime.total_seconds()))
        except REDIS_FAILURES as error:
            raise SocialStateUnavailableError from error

    async def _getdel(self, key: str) -> dict[str, str] | None:
        try:
            async with asyncio.timeout(DEADLINE.total_seconds()):
                value = await self._valkey.getdel(key)
        except REDIS_FAILURES as error:
            raise SocialStateUnavailableError from error
        if value is None:
            return None
        payload: dict[str, str] = json.loads(value)
        return payload


def _digest(ticket: str) -> str:
    return hashlib.sha256(ticket.encode("utf-8")).hexdigest()


def _key(kind: str, name: str) -> str:
    return build_key("identity", kind, name)

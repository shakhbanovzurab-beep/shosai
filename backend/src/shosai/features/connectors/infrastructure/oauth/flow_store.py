"""Started connect flows in Valkey: 10 minutes, taken once (connectors plan §3.4).

A flow is kept under the SHA-256 of its state, so a copy of the store holds no state a
browser could replay; `GETDEL` takes it once, so a replayed callback finds nothing — the
draft's GET then DELETE let two callbacks race. Nothing personal is written: ids, a home,
an app, the PKCE verifier, the binder's digest, the scopes asked for and the return path.
A flow is never written to the database: an abandoned one simply expires.
"""

import asyncio
import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Final
from uuid import UUID

import structlog
from redis.asyncio import Redis

from shosai.core.kernel.homes import Home
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.kv.keys import build_key
from shosai.features.connectors.domain.catalogue import App, Owner
from shosai.features.connectors.domain.flows import (
    FLOW_LIFETIME,
    ReturnKind,
    ReturnTarget,
    digest_of,
)

DEADLINE: Final = timedelta(milliseconds=200)
log = structlog.stdlib.get_logger(__name__)


class FlowStoreUnavailableError(Exception):
    """Valkey did not answer: a connect flow cannot start or finish now."""


@dataclass(frozen=True, slots=True)
class FlowRecord:
    """One started flow, as the callback needs it."""

    user_id: UUID
    home: Home
    org_id: UUID | None
    app: App
    client_key: str
    verifier: str
    binder_digest: str
    target: ReturnTarget
    scopes: frozenset[str]
    # Переустановка пространства или переподключение: какое подключение заменяется.
    replaces: UUID | None = None

    @property
    def owner(self) -> Owner:
        """Who the grant will belong to."""
        return Owner.PERSON if self.org_id is None else Owner.WORKSPACE


def encode(flow: FlowRecord) -> str:
    """The flow as stored: plain JSON of ids and codes."""
    return json.dumps({
        "user_id": str(flow.user_id), "home": flow.home.value,
        "org_id": None if flow.org_id is None else str(flow.org_id), "app": flow.app.value,
        "client_key": flow.client_key, "verifier": flow.verifier,
        "binder": flow.binder_digest, "return": flow.target.kind.value,
        "path": flow.target.path, "scopes": sorted(flow.scopes),
        "replaces": None if flow.replaces is None else str(flow.replaces),
    })  # fmt: skip


def decode(value: str | bytes) -> FlowRecord:
    """A stored flow back; a malformed one raises `ValueError`."""
    raw = json.loads(value)
    org, replaces = raw["org_id"], raw["replaces"]
    return FlowRecord(
        user_id=UUID(raw["user_id"]), home=Home(raw["home"]),
        org_id=None if org is None else UUID(org), app=App(raw["app"]),
        client_key=str(raw["client_key"]), verifier=str(raw["verifier"]),
        binder_digest=str(raw["binder"]),
        target=ReturnTarget(ReturnKind(raw["return"]), raw["path"]),
        scopes=frozenset(raw["scopes"]), replaces=None if replaces is None else UUID(replaces),
    )  # fmt: skip


class FlowStore:
    """Connect flows under the digest of their state."""

    def __init__(self, valkey: Redis) -> None:
        self._valkey = valkey

    async def open(self, nonce: str, flow: FlowRecord) -> None:
        """Keep a flow for 10 minutes under its state."""
        try:
            async with asyncio.timeout(DEADLINE.total_seconds()):
                await self._valkey.set(
                    _key(nonce), encode(flow), ex=int(FLOW_LIFETIME.total_seconds())
                )
        except REDIS_FAILURES as error:
            raise FlowStoreUnavailableError from error

    async def take(self, nonce: str) -> FlowRecord | None:
        """The flow of a state, once; None when it expired, was taken or never existed."""
        try:
            async with asyncio.timeout(DEADLINE.total_seconds()):
                value = await self._valkey.getdel(_key(nonce))
        except REDIS_FAILURES as error:
            raise FlowStoreUnavailableError from error
        if value is None:
            return None
        try:
            return decode(value)
        except (ValueError, KeyError, TypeError) as error:
            # Запись повреждена или старого формата: поток считается истёкшим.
            log.warning("Поток подключения не читается", error=type(error).__name__)
            return None


def _key(nonce: str) -> str:
    return build_key("connectors", "flow", digest_of(nonce))

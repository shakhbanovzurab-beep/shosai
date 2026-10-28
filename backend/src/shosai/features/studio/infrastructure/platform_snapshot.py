"""The platform's catalogue, defaults and published layer as one process holds them.

Every resolution reads the catalogue and every prompt the published layer, so a process keeps
them for a minute and reads them again in one transaction of the EU home, one reader at a
time: about thirty processes read them once a minute between them (studio plan §2, §1.3).
An operator's change reaches every process within that minute, as the screens say; the
process that made it drops its own copy at once. There is nothing to invalidate across
processes, so nothing can be invalidated wrong.
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import timedelta
from types import MappingProxyType
from typing import Final

from prometheus_client import CollectorRegistry, Gauge
from sqlalchemy import select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.studio.domain.platform_layer import BUILT_IN, PlatformConfig
from shosai.features.studio.domain.routing import Catalogue
from shosai.features.studio.infrastructure.catalogue_store import default_of, model_of
from shosai.features.studio.infrastructure.platform_config_codec import config_of
from shosai.features.studio.infrastructure.platform_records import (
    CatalogueRecord,
    PlatformVersionRecord,
    RoleDefaultRecord,
)

SNAPSHOT_TTL: Final = timedelta(seconds=60)


@dataclass(frozen=True, slots=True)
class PublishedLayer:
    """The live version's number and config; none and built-in before the first publish."""

    version: int | None
    config: PlatformConfig


@dataclass(frozen=True, slots=True)
class _Snapshot:
    catalogue: Catalogue
    layer: PublishedLayer
    taken_at: float


class PlatformSnapshot:
    """The catalogue, the defaults and the published layer, read at most once a minute."""

    def __init__(
        self,
        transactions: HomeTransactions,
        registry: CollectorRegistry,
        ttl: timedelta = SNAPSHOT_TTL,
    ) -> None:
        self._transactions = transactions
        self._ttl = ttl.total_seconds()
        self._snapshot: _Snapshot | None = None
        self._lock = asyncio.Lock()
        self._age = Gauge(
            "shosai_studio_snapshot_age_seconds",
            "Age of the platform catalogue this process resolves models from",
            registry=registry,
        )
        self._age.set_function(self._age_seconds)

    async def catalogue(self) -> Catalogue:
        """The catalogue and defaults no older than a minute."""
        return (await self._current()).catalogue

    async def published(self) -> PublishedLayer:
        """The published layer no older than a minute."""
        return (await self._current()).layer

    async def _current(self) -> _Snapshot:
        snapshot = self._snapshot
        if snapshot is not None and time.monotonic() - snapshot.taken_at < self._ttl:
            return snapshot
        # Один процесс — одно чтение: остальные ждут его, а не идут в базу вслед.
        async with self._lock:
            snapshot = self._snapshot
            if snapshot is None or time.monotonic() - snapshot.taken_at >= self._ttl:
                snapshot = await self._read()
                self._snapshot = snapshot
        return snapshot

    def drop(self) -> None:
        """Forget this process's copy after its own write; the next read is fresh."""
        self._snapshot = None

    async def _read(self) -> _Snapshot:
        async with self._transactions.begin(TenancyScope(Home.EU), read_only=True) as session:
            models = (await session.scalars(select(CatalogueRecord))).all()
            defaults = (await session.scalars(select(RoleDefaultRecord))).all()
            version = await session.scalar(
                select(PlatformVersionRecord).order_by(PlatformVersionRecord.number.desc()).limit(1)
            )
        catalogue = Catalogue(
            MappingProxyType({row.id: model_of(row) for row in models}),
            MappingProxyType({default.role: default for default in map(default_of, defaults)}),
        )
        layer = (
            PublishedLayer(version.number, config_of(version.config))
            if version is not None
            else PublishedLayer(None, BUILT_IN)
        )
        return _Snapshot(catalogue, layer, time.monotonic())

    def _age_seconds(self) -> float:
        snapshot = self._snapshot
        return 0.0 if snapshot is None else time.monotonic() - snapshot.taken_at

"""Which policy version answers a point now, and with which cuts (decisions plan §3.3 step 1).

The versions in force are read from the EU home at most once a minute per process. A read
that fails keeps the last good copy; with none ever read, nothing is in force and every
point runs its rule. A stored version the code does not have, or whose questions' wording
differs from the code's, is not in force: thresholds fitted to other questions never judge
these ones. Its cuts must also name every cut the policy reads.
"""

import asyncio
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Final, Protocol

import structlog

from shosai.features.decisions.domain.policy import Policy
from shosai.features.decisions.domain.verdicts import Cut

FRESH_FOR: Final = timedelta(seconds=60)
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class StoredPolicy:
    """A version in force as stored: its state, the revision it uses and that revision's cuts."""

    point: str
    version: int
    state: str
    revision: int
    digest: str
    cuts: Mapping[str, Cut]


@dataclass(frozen=True, slots=True)
class InForce:
    """A policy version that judges, the revision it uses and that revision's cuts."""

    policy: Policy[Any, Any]
    revision: int
    cuts: Mapping[str, Cut]


@dataclass(frozen=True, slots=True)
class PointInForce:
    """A point's active version and its shadow, either absent."""

    active: InForce | None = None
    shadow: InForce | None = None


class PoliciesUnreadableError(Exception):
    """The store could not be read: the home is down or the read failed."""


class StoredPolicies(Protocol):
    """Where the versions in force are kept."""

    async def in_force(self) -> Sequence[StoredPolicy]:
        """Every version in shadow or active; `PoliciesUnreadableError` when unreadable."""
        ...


@dataclass(slots=True)
class _Copy:
    points: dict[str, PointInForce] = field(default_factory=dict)
    read_at: float | None = None


class PoliciesInForce:
    """The versions in force by point, read once a minute, the last good copy kept."""

    def __init__(
        self,
        store: StoredPolicies,
        policies: Mapping[str, Policy[Any, Any]],
        clock: Callable[[], float] = time.monotonic,
        fresh_for: timedelta = FRESH_FOR,
    ) -> None:
        self._store = store
        self._policies = policies
        self._clock = clock
        self._fresh_for = fresh_for.total_seconds()
        self._copy = _Copy()
        self._lock = asyncio.Lock()

    async def of(self, point: str) -> PointInForce:
        """The point's versions in force; empty when none is."""
        if self._stale():
            async with self._lock:
                if self._stale():
                    await self._refresh()
        return self._copy.points.get(point, PointInForce())

    def _stale(self) -> bool:
        read_at = self._copy.read_at
        return read_at is None or self._clock() - read_at >= self._fresh_for

    async def _refresh(self) -> None:
        try:
            stored = await self._store.in_force()
        except PoliciesUnreadableError:
            # Прежняя копия остаётся; следующая попытка — через тот же срок.
            self._copy.read_at = self._clock()
            log.warning("Политики решений не прочитаны: решает прежняя копия")
            return
        self._copy = _Copy(points=self.arrange(stored), read_at=self._clock())

    def arrange(self, stored: Sequence[StoredPolicy]) -> dict[str, PointInForce]:
        """The stored versions this code can judge with, by point."""
        points: dict[str, PointInForce] = {}
        for row in stored:
            judged = self._usable(row)
            if judged is None:
                continue
            current = points.get(row.point, PointInForce())
            if row.state == "active":
                points[row.point] = PointInForce(active=judged, shadow=current.shadow)
            else:
                points[row.point] = PointInForce(active=current.active, shadow=judged)
        return points

    def _usable(self, row: StoredPolicy) -> InForce | None:
        policy = self._policies.get(f"{row.point}@{row.version}")
        if policy is None or policy.digest() != row.digest:
            log.error("Политика в силе не совпадает с кодом", point=row.point, version=row.version)
            return None
        if not set(policy.cuts) <= set(row.cuts):
            log.error("Ревизии не хватает порогов", point=row.point, version=row.version)
            return None
        return InForce(policy, row.revision, row.cuts)

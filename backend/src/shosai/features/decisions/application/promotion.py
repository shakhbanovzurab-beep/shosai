"""Putting a policy version in force, and taking it out (decisions plan §3.5, DL-D6).

A version goes to `shadow` with a revision whose report passed every gate and whose questions'
wording is this code's. It goes to `active` only from shadow, with the same revision, after
its shadow window: two weeks and 5 000 shadow decisions, whichever comes later (Leo §6.4) —
or, for the version already active, with a new passing revision of the same wording, since
new cuts replay exactly over the same answers. `retire` takes a version out at once; the
point runs its rule within the engine's minute.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any, Final, Protocol

from shosai.features.decisions.domain.policy import Policy
from shosai.features.decisions.infrastructure.policy_admin import StoredRevision, VersionState

SHADOW_DAYS: Final = timedelta(days=14)
UTC_NOW: Final = partial(datetime.now, UTC)
SHADOW_DECISIONS: Final = 5_000


class Admin(Protocol):
    """Revisions, states and the shadow's count."""

    async def revision(self, point: str, version: int, number: int) -> StoredRevision | None:
        """One revision, or None."""
        ...

    async def states(self, point: str) -> Sequence[VersionState]:
        """Every version of a point that was ever in force."""
        ...

    async def set_state(
        self, target: tuple[str, int, int, str], digest: str, note: str | None
    ) -> None:
        """Put a version with a revision in a state."""
        ...

    async def shadow_decisions(self, point: str, version: int, since: datetime) -> int:
        """The shadow's decisions since a moment."""
        ...


@dataclass(frozen=True, slots=True)
class Refusal:
    """Why a promotion was refused, in words for the operator."""

    reason: str


class Promotion:
    """Promotes and retires policy versions."""

    def __init__(
        self,
        admin: Admin,
        policies: Mapping[str, Policy[Any, Any]],
        now: Callable[[], datetime] = UTC_NOW,
    ) -> None:
        self._admin = admin
        self._policies = policies
        self._now = now

    async def promote(
        self, key: str, revision: int, state: str, note: str | None
    ) -> Refusal | None:
        """Put `point@version` with a revision in shadow or active; why not, if refused."""
        policy = self._policies.get(key)
        if policy is None:
            return Refusal(f"версии {key} нет в коде этого образа")
        stored = await self._admin.revision(policy.point, policy.version, revision)
        if stored is None:
            return Refusal(f"у {key} нет ревизии {revision}")
        if stored.digest != policy.digest():
            return Refusal("ревизия подобрана к другим формулировкам вопросов")
        if not stored.passed:
            failed = ", ".join(stored.report.get("failures", [])) or "без отчёта"
            return Refusal(f"ревизия не прошла пороги: {failed}")
        if state == "active":
            refusal = await self._window(policy, revision)
            if refusal is not None:
                return refusal
        target = (policy.point, policy.version, revision, state)
        await self._admin.set_state(target, policy.digest(), note)
        return None

    async def retire(self, key: str, note: str | None) -> Refusal | None:
        """Take a version out of force; the point runs its rule within a minute."""
        policy = self._policies.get(key)
        if policy is None:
            return Refusal(f"версии {key} нет в коде этого образа")
        current = await self._state(policy)
        if current is None:
            return Refusal(f"версия {key} не была в силе")
        target = (policy.point, policy.version, current.revision, "retired")
        await self._admin.set_state(target, policy.digest(), note)
        return None

    async def _window(self, policy: Policy[Any, Any], revision: int) -> Refusal | None:
        """Active only after the shadow window, or as a new revision of the active version."""
        current = await self._state(policy)
        if current is not None and current.state == "active":
            return None
        if current is None or current.state != "shadow" or current.revision != revision:
            return Refusal("в силу — только из тени с той же ревизией")
        since = current.changed_at
        if self._now() - since < SHADOW_DAYS:
            return Refusal(f"тень с {since:%Y-%m-%d}: две недели ещё не прошли")
        seen = await self._admin.shadow_decisions(policy.point, policy.version, since)
        if seen < SHADOW_DECISIONS:
            return Refusal(f"в тени {seen} решений из {SHADOW_DECISIONS}")
        return None

    async def _state(self, policy: Policy[Any, Any]) -> VersionState | None:
        """The version's state row, if it was ever in force."""
        for state in await self._admin.states(policy.point):
            if state.version == policy.version:
                return state
        return None

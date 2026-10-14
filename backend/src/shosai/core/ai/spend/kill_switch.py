"""The kill switch: expensive AI calls paused platform-wide (§3.6, F6-D5).

Engaged by the setting `AI_KILL_SWITCH`, or by an operator through this service for a time
(24 hours unless said otherwise): a key in Valkey with that TTL holds who engaged it and
why. While it is engaged an expensive call is refused with `expensive_paused`, or takes the
standard model its route names; essential and standard calls never notice it. The service
is what `studio`'s AI models screen and the CLI `shosai ai kill-switch` call; every change
writes one log line with the operator and the reason.
"""

import asyncio
import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Final

import structlog
from redis.asyncio import Redis

from shosai.core.kv.keys import build_key

KILL_SWITCH_KEY: Final = build_key("ai", "kill_switch")
DEFAULT_TTL: Final = timedelta(hours=24)
VALKEY_DEADLINE: Final = 1.0
REASON_MAX: Final = 200
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class KillSwitchState:
    """Whether expensive calls are paused, by what, by whom, why, and for how long."""

    engaged: bool
    by_setting: bool
    actor: str | None = None
    reason: str | None = None
    left: timedelta | None = None


class KillSwitch:
    """Engages, releases and reports the kill switch."""

    def __init__(self, client: Redis, *, forced: bool) -> None:
        self._client = client
        self._forced = forced

    @property
    def forced(self) -> bool:
        """Engaged by the setting, whatever Valkey holds."""
        return self._forced

    async def engage(self, actor: str, reason: str, ttl: timedelta = DEFAULT_TTL) -> None:
        """Pause expensive calls for `ttl`; `actor` is the operator's id or `cli`."""
        if not reason.strip() or len(reason) > REASON_MAX or ttl <= timedelta(0):
            message = "выключателю нужна причина до 200 символов и срок больше нуля"
            raise ValueError(message)
        value = json.dumps({"actor": actor, "reason": reason}, ensure_ascii=False)
        async with asyncio.timeout(VALKEY_DEADLINE):
            await self._client.set(KILL_SWITCH_KEY, value, px=int(ttl.total_seconds() * 1000))
        log.warning(
            "Аварийный выключатель ИИ включён", actor=actor, reason=reason,
            ttl_seconds=int(ttl.total_seconds()),
        )  # fmt: skip

    async def release(self, actor: str) -> None:
        """Resume expensive calls; the setting, if it engages the switch, still holds."""
        async with asyncio.timeout(VALKEY_DEADLINE):
            await self._client.delete(KILL_SWITCH_KEY)
        log.warning("Аварийный выключатель ИИ выключен", actor=actor, by_setting=self._forced)

    async def state(self) -> KillSwitchState:
        """What holds now."""
        async with asyncio.timeout(VALKEY_DEADLINE):
            value = await self._client.get(KILL_SWITCH_KEY)
            left_ms = await self._client.pttl(KILL_SWITCH_KEY)
        if value is None:
            return KillSwitchState(engaged=self._forced, by_setting=self._forced)
        held = json.loads(value)
        return KillSwitchState(
            engaged=True,
            by_setting=self._forced,
            actor=str(held.get("actor")),
            reason=str(held.get("reason")),
            left=timedelta(milliseconds=left_ms) if left_ms > 0 else None,
        )

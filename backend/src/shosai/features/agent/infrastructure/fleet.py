"""The agent workers' fleet and the runs it holds, counted in Valkey (Leo §12, AG-D12).

A worker of the `agent` queue says every 10 s that it is alive; the fleet's capacity is 48
runs for each worker alive. A turn is admitted with one script: it drops lapsed members,
then refuses it when the person already has two runs, or when the fleet's admitted runs fill
its capacity — so a turn waits in no queue, it is refused with `agent_busy` — and otherwise
counts it for the fleet and the person. A run's worker renews the counts with its lease and
drops them when the run ends; a lost worker's runs lapse in 30 s.
"""

import time
from collections.abc import Collection
from enum import StrEnum
from typing import Final
from uuid import UUID

from redis.asyncio import Redis
from redis.typing import EncodableT

from shosai.features.agent.domain.runs import LEASE_TTL, RUNS_PER_PERSON, RUNS_PER_WORKER
from shosai.features.agent.infrastructure.run_keys import (
    FLEET_RUNS,
    FLEET_WORKERS,
    person_runs_key,
)

# Ключи: прогоны парка, прогоны человека, воркеры. Аргументы: сейчас, прогон, когда он
# истечёт, сколько прогонов человеку, сколько воркеру — всё в миллисекундах и штуках.
ADMIT_SCRIPT: Final = """
local now = tonumber(ARGV[1])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
redis.call('ZREMRANGEBYSCORE', KEYS[2], '-inf', now)
redis.call('ZREMRANGEBYSCORE', KEYS[3], '-inf', now)
if redis.call('ZCARD', KEYS[2]) >= tonumber(ARGV[4]) then
  return 'too_many_runs'
end
local capacity = redis.call('ZCARD', KEYS[3]) * tonumber(ARGV[5])
if redis.call('ZCARD', KEYS[1]) >= capacity then
  return 'agent_busy'
end
redis.call('ZADD', KEYS[1], ARGV[3], ARGV[2])
redis.call('ZADD', KEYS[2], ARGV[3], ARGV[2])
redis.call('PEXPIREAT', KEYS[2], ARGV[3])
return 'admitted'
"""


class Admission(StrEnum):
    """What the fleet said to a turn; the refusals are the API's codes."""

    ADMITTED = "admitted"
    TOO_MANY_RUNS = "too_many_runs"
    AGENT_BUSY = "agent_busy"


def now_ms() -> int:
    """The wall clock in milliseconds, the score unit of the fleet's sets."""
    return time.time_ns() // 1_000_000


def lapse_ms() -> int:
    """When a member written now lapses unless renewed."""
    return now_ms() + int(LEASE_TTL.total_seconds() * 1000)


class Fleet:
    """Admits runs against the person's and the fleet's limits and keeps the counts."""

    def __init__(self, valkey: Redis) -> None:
        self._valkey = valkey
        self._admit = valkey.register_script(ADMIT_SCRIPT)

    async def admit(self, user_id: UUID, run_id: UUID) -> Admission:
        """Count a new run, or say why it may not start now."""
        keys = [FLEET_RUNS, person_runs_key(user_id), FLEET_WORKERS]
        args: list[EncodableT] = [
            now_ms(), str(run_id), lapse_ms(), RUNS_PER_PERSON, RUNS_PER_WORKER,
        ]  # fmt: skip
        answer = await self._admit(keys=keys, args=args)
        return Admission(answer.decode() if isinstance(answer, bytes) else answer)

    async def renew(self, runs: Collection[tuple[UUID, UUID]]) -> None:
        """Keep counting runs still driven, given as (person, run)."""
        if not runs:
            return
        lapse = lapse_ms()
        async with self._valkey.pipeline(transaction=False) as pipeline:
            for user_id, run_id in runs:
                await pipeline.zadd(FLEET_RUNS, {str(run_id): lapse}, xx=True)
                await pipeline.zadd(person_runs_key(user_id), {str(run_id): lapse}, xx=True)
                await pipeline.pexpireat(person_runs_key(user_id), lapse)
            await pipeline.execute()

    async def release(self, user_id: UUID, run_id: UUID) -> None:
        """Stop counting a run that is over or was never started."""
        async with self._valkey.pipeline(transaction=False) as pipeline:
            await pipeline.zrem(FLEET_RUNS, str(run_id))
            await pipeline.zrem(person_runs_key(user_id), str(run_id))
            await pipeline.execute()

    async def alive(self, worker: str) -> None:
        """A worker of the `agent` queue says it is alive for the next 30 s."""
        await self._valkey.zadd(FLEET_WORKERS, {worker: lapse_ms()})

    async def gone(self, worker: str) -> None:
        """A stopping worker takes no new runs: it leaves the fleet's capacity at once."""
        await self._valkey.zrem(FLEET_WORKERS, worker)

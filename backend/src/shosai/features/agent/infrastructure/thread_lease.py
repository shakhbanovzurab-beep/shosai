"""A thread's lease and a run's stop request in Valkey (Leo §5.2 step 3, §12).

The lease holds the id of the one run a thread has: taken with `SET NX PX` when a turn is
admitted, renewed every 10 s by the run's worker, released by the run's end — each renewal
and release compares the holder first, so a run never renews or frees another run's lease.
A lease nobody renews lapses in 30 s. A stop request is a flag the run's worker reads twice a
second: "Stop", a superseding turn or a deleted thread sets it.
"""

from collections.abc import Collection, Sequence
from datetime import timedelta
from typing import Final
from uuid import UUID

from redis.asyncio import Redis

from shosai.features.agent.domain.runs import LEASE_TTL
from shosai.features.agent.infrastructure.run_keys import lease_key, stop_key

RENEW_SCRIPT: Final = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('PEXPIRE', KEYS[1], ARGV[2])
end
return 0
"""
RELEASE_SCRIPT: Final = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""
# Флаг остановки живёт дольше любого хода: воркер прочтёт его, даже если ход ещё в очереди.
STOP_TTL: Final = timedelta(minutes=5)


def lease_ms() -> int:
    """The lease's time to live in milliseconds."""
    return int(LEASE_TTL.total_seconds() * 1000)


class ThreadLeases:
    """Takes, renews and frees threads' leases; sets and reads runs' stop requests."""

    def __init__(self, valkey: Redis) -> None:
        self._valkey = valkey
        self._renew = valkey.register_script(RENEW_SCRIPT)
        self._release = valkey.register_script(RELEASE_SCRIPT)

    async def take(self, thread_id: UUID, run_id: UUID) -> bool:
        """Lease the thread to the run unless another run holds it."""
        taken = await self._valkey.set(lease_key(thread_id), str(run_id), nx=True, px=lease_ms())
        return bool(taken)

    async def holder(self, thread_id: UUID) -> UUID | None:
        """The run holding the thread now."""
        value = await self._valkey.get(lease_key(thread_id))
        if value is None:
            return None
        return UUID(value.decode() if isinstance(value, bytes) else value)

    async def renew(self, leases: Collection[tuple[UUID, UUID]]) -> set[UUID]:
        """Renew (thread, run) leases; the runs that no longer hold theirs."""
        pairs = list(leases)
        if not pairs:
            return set()
        async with self._valkey.pipeline(transaction=False) as pipeline:
            for thread_id, run_id in pairs:
                await self._renew(
                    keys=[lease_key(thread_id)], args=[str(run_id), lease_ms()], client=pipeline
                )
            renewed = await pipeline.execute()
        return {run_id for (_, run_id), done in zip(pairs, renewed, strict=True) if not done}

    async def release(self, thread_id: UUID, run_id: UUID) -> None:
        """Free the thread if the run still holds it."""
        await self._release(keys=[lease_key(thread_id)], args=[str(run_id)])

    async def ask_to_stop(self, run_id: UUID) -> None:
        """Ask the run to stop; repeated asks change nothing."""
        await self._valkey.set(stop_key(run_id), "1", ex=STOP_TTL)

    async def stops_asked(self, run_ids: Sequence[UUID]) -> set[UUID]:
        """Which of the runs were asked to stop, in one round trip."""
        if not run_ids:
            return set()
        flags = await self._valkey.mget([stop_key(run_id) for run_id in run_ids])
        return {run_id for run_id, flag in zip(run_ids, flags, strict=True) if flag is not None}

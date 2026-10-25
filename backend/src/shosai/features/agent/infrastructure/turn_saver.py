"""Our saver of a turn's frame (ADR 0068 AG-D14, Leo §10): one Valkey hash per run in flight.

LangGraph hands its checkpoints to the saver through the public `BaseCheckpointSaver`
interface after every step, in the background of the next one, and the hash keeps the run's
latest checkpoint: its metadata, the writes LangGraph needs to resume — the interrupt among
them — and its channel values, of which a step writes only those it changed (Leo §10's
checkpoint discipline). The state holds references only, never the conversation. A turn goes
on from its latest checkpoint, so no history is kept; the engine deletes the key when the run
ends, and a paused run's key lives as long as its card can be decided. Erasing a person's runs
deletes it with their other keys. A Valkey that does not answer costs the epilogue, never the
turn or the card: the decision then ends the run with its server note (Leo §5.3 step 4).
"""

from collections.abc import AsyncIterator, Sequence
from datetime import timedelta
from typing import Any, Final
from uuid import UUID

import structlog
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
    get_checkpoint_metadata,
)
from redis.asyncio import Redis
from redis.typing import EncodableT

from shosai.core.kv.connection import REDIS_FAILURES
from shosai.features.agent.domain.runs import PAUSED_LOG
from shosai.features.agent.infrastructure.run_keys import checkpoint_key
from shosai.features.agent.infrastructure.turn_frame_fields import (
    CHECKPOINT,
    ID,
    METADATA,
    WRITE,
    as_bytes,
    packed,
    unpacked,
    value_field,
    values_of,
    versioned,
    write_field,
    write_of,
    writes_of,
)

# Ключ кадра; аргументы: срок в мс, id новой точки, пары поле — значение (пустое удаляет поле).
# Точка не старше сохранённой, иначе ничего; записи более ранних точек к ней не относятся.
PUT_SCRIPT: Final = f"""
local current = redis.call('HGET', KEYS[1], 'id')
if current and current > ARGV[2] then
  return 0
end
for _, field in ipairs(redis.call('HKEYS', KEYS[1])) do
  if string.sub(field, 1, {len(WRITE)}) == '{WRITE}' then
    local owner = string.sub(field, {len(WRITE) + 1}, {len(WRITE)} + string.len(ARGV[2]))
    if owner < ARGV[2] then
      redis.call('HDEL', KEYS[1], field)
    end
  end
end
for i = 3, #ARGV, 2 do
  if ARGV[i + 1] == '' then
    redis.call('HDEL', KEYS[1], ARGV[i])
  else
    redis.call('HSET', KEYS[1], ARGV[i], ARGV[i + 1])
  end
end
redis.call('PEXPIRE', KEYS[1], ARGV[1])
return 1
"""
log = structlog.stdlib.get_logger(__name__)


def run_of(config: RunnableConfig) -> UUID | None:
    """The run a frame's config names; None for a nested graph, which a turn never has."""
    configurable = config.get("configurable") or {}
    if configurable.get("checkpoint_ns", ""):
        return None
    thread = configurable.get("thread_id")
    return UUID(str(thread)) if thread is not None else None


def frame(run_id: UUID, checkpoint_id: str) -> RunnableConfig:
    """The config of a run's checkpoint."""
    return {
        "configurable": {
            "thread_id": str(run_id),
            "checkpoint_ns": "",
            "checkpoint_id": checkpoint_id,
        }
    }


class TurnSaver(BaseCheckpointSaver[int]):
    """Keeps the frame of each run in flight in Valkey."""

    def __init__(self, valkey: Redis, ttl: timedelta = PAUSED_LOG) -> None:
        super().__init__()
        self._valkey = valkey
        self._put = valkey.register_script(PUT_SCRIPT)
        self._ttl_ms = int(ttl.total_seconds() * 1000)

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """The run's latest checkpoint, or None when it keeps none or not the one asked."""
        run_id = run_of(config)
        if run_id is None:
            return None
        try:
            raw = await self._valkey.hgetall(checkpoint_key(run_id))
        except REDIS_FAILURES as error:
            # Кадр не прочитан — как будто его нет: новый ход начнётся, а эпилога не будет.
            log.warning("Кадр хода Leo не прочитан", error_type=type(error).__name__)
            return None
        saved = {as_bytes(field): as_bytes(value) for field, value in raw.items()}
        if CHECKPOINT not in saved or ID not in saved:
            return None
        checkpoint_id = saved[ID].decode()
        wanted = get_checkpoint_id(config)
        if wanted is not None and wanted != checkpoint_id:
            return None
        loads = self.serde.loads_typed
        checkpoint: Checkpoint = loads(unpacked(saved[CHECKPOINT]))
        checkpoint["channel_values"] = values_of(saved, checkpoint["channel_versions"], loads)
        return CheckpointTuple(
            config=frame(run_id, checkpoint_id),
            checkpoint=checkpoint,
            metadata=loads(unpacked(saved[METADATA])),
            parent_config=None,
            pending_writes=writes_of(saved, checkpoint_id, loads),
        )

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """The run's one checkpoint, when it matches the filter and comes before `before`."""
        found = await self.aget_tuple(config) if config is not None else None
        if found is None or limit == 0:
            return
        older = get_checkpoint_id(before) if before is not None else None
        if older is not None and found.checkpoint["id"] >= older:
            return
        if filter and any(found.metadata.get(key) != value for key, value in filter.items()):
            return
        yield found

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Keep the checkpoint as the run's only one, with the channels this step changed."""
        run_id = run_of(config)
        if run_id is None:
            message = "сохранитель хода держит только кадры прогонов"
            raise ValueError(message)
        dumps = self.serde.dumps_typed
        values = checkpoint["channel_values"]
        shape = {**checkpoint, "channel_values": {}}
        fields: list[EncodableT] = [
            ID, checkpoint["id"].encode(),
            CHECKPOINT, packed(dumps(shape)),
            METADATA, packed(dumps(get_checkpoint_metadata(config, metadata))),
        ]  # fmt: skip
        for channel, version in new_versions.items():
            changed = versioned(version, dumps(values[channel])) if channel in values else b""
            fields += [value_field(channel), changed]
        try:
            await self._put(
                keys=[checkpoint_key(run_id)], args=[self._ttl_ms, checkpoint["id"], *fields]
            )
        except REDIS_FAILURES as error:
            # Карточка в базе: решение исполнится, а прогон закроется заметкой без эпилога.
            log.warning("Кадр хода Leo не сохранён", error_type=type(error).__name__)
        return frame(run_id, checkpoint["id"])

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Keep a task's writes under the checkpoint they belong to; a write kept stays."""
        run_id = run_of(config)
        checkpoint_id = get_checkpoint_id(config)
        if run_id is None or checkpoint_id is None:
            return
        key = checkpoint_key(run_id)
        try:
            async with self._valkey.pipeline(transaction=True) as pipeline:
                for number, (channel, value) in enumerate(writes):
                    index = WRITES_IDX_MAP.get(channel, number)
                    field = write_field(checkpoint_id, task_id, index)
                    kept = write_of(channel, task_path, self.serde.dumps_typed(value))
                    # Особые записи (прерывание, ошибка) заменяются, обычные — нет, как у LangGraph.
                    if index < 0:
                        await pipeline.hset(key, field, kept)
                    else:
                        await pipeline.hsetnx(key, field, kept)
                await pipeline.pexpire(key, self._ttl_ms)
                await pipeline.execute()
        except REDIS_FAILURES as error:
            log.warning("Записи кадра хода Leo не сохранены", error_type=type(error).__name__)

    async def adelete_thread(self, thread_id: str) -> None:
        """Delete a run's frame."""
        await self._valkey.delete(checkpoint_key(UUID(thread_id)))

    async def forget(self, run_id: UUID) -> None:
        """Delete the frame a run no longer needs: it ended, or its card ended without an
        epilogue. A Valkey that does not answer leaves the key to its hour."""
        try:
            await self.adelete_thread(str(run_id))
        except REDIS_FAILURES as error:
            log.warning("Кадр хода Leo не удалён", error_type=type(error).__name__)

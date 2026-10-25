"""The fields of a run's frame in its Valkey hash (agent step 9a2): how each is written and read.

The hash holds the latest checkpoint's id, the checkpoint without its values, its metadata,
one field per channel with the version of its value — so a step writes only the channels it
changed (Leo §10: channel-version deduplication) — and one field per pending write, named by
the checkpoint it belongs to, since LangGraph may write a step's writes before the checkpoint
itself. A value is kept with its serializer's type before its bytes; the parts of a field are
joined by a zero byte, which no type or channel name holds.
"""

from collections.abc import Callable, Mapping
from typing import Any, Final

ID: Final = b"id"
CHECKPOINT: Final = b"checkpoint"
METADATA: Final = b"metadata"
# Поле канала: префикс и имя канала; значение — версия, тип и байты.
VALUE: Final = "v|"
# Поле записи: префикс, контрольная точка, задача и номер; значение — канал, путь, тип и байты.
WRITE: Final = "w|"
SEPARATOR: Final = b"\x00"

type Loads = Callable[[tuple[str, bytes]], Any]
type Write = tuple[str, str, Any]


def as_bytes(value: bytes | str) -> bytes:
    """A value Valkey gave back, as bytes."""
    return value if isinstance(value, bytes) else value.encode()


def packed(typed: tuple[str, bytes]) -> bytes:
    """A serialized value with its type, as one field."""
    kind, data = typed
    return kind.encode() + SEPARATOR + data


def unpacked(raw: bytes) -> tuple[str, bytes]:
    """A field back into its type and bytes."""
    kind, _, data = raw.partition(SEPARATOR)
    return kind.decode(), data


def value_field(channel: str) -> str:
    """The field of a channel's value."""
    return f"{VALUE}{channel}"


def versioned(version: str | int | float, typed: tuple[str, bytes]) -> bytes:
    """A channel's value with the version it was written at."""
    return str(version).encode() + SEPARATOR + packed(typed)


def values_of(
    saved: Mapping[bytes, bytes], versions: Mapping[str, str | int | float], loads: Loads
) -> dict[str, Any]:
    """The checkpoint's channel values: each at the version the checkpoint names, if kept."""
    values: dict[str, Any] = {}
    for channel, version in versions.items():
        raw = saved.get(value_field(channel).encode())
        if raw is None:
            continue
        kept, _, typed = raw.partition(SEPARATOR)
        if kept.decode() == str(version):
            values[channel] = loads(unpacked(typed))
    return values


def write_field(checkpoint_id: str, task_id: str, index: int) -> str:
    """The field of one pending write of a checkpoint."""
    return f"{WRITE}{checkpoint_id}|{task_id}|{index}"


def write_of(channel: str, task_path: str, typed: tuple[str, bytes]) -> bytes:
    """A pending write as one field: its channel, its task's path, its value with its type."""
    return SEPARATOR.join((channel.encode(), task_path.encode(), packed(typed)))


def writes_of(saved: Mapping[bytes, bytes], checkpoint_id: str, loads: Loads) -> list[Write]:
    """The checkpoint's pending writes in LangGraph's order: by task, then by number."""
    prefix = f"{WRITE}{checkpoint_id}|"
    found: list[tuple[str, int, Write]] = []
    for field, value in saved.items():
        name = field.decode()
        if not name.startswith(prefix):
            continue
        task_id, _, index = name.removeprefix(prefix).rpartition("|")
        channel, _, rest = value.partition(SEPARATOR)
        _, _, typed = rest.partition(SEPARATOR)
        found.append((task_id, int(index), (task_id, channel.decode(), loads(unpacked(typed)))))
    return [write for _, _, write in sorted(found, key=lambda each: (each[0], each[1]))]

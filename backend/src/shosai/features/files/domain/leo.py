"""Whether Leo uses a file, and the knowledge limit (cabinet: `knowledge-base-api.md`).

Leo uses a file it can read when the file's own switch or its folder's is on, and says
which. The bytes of every file Leo uses count against the plan's `knowledge_base_mb`
(None: unlimited, 0: not included); a change that starts using a file is refused when the
bytes in use would pass it. Files Leo cannot read never count, whatever their switches.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final
from uuid import UUID

from shosai.features.files.domain.kinds import leo_readable

MIB: Final = 1024**2


class LeoVia(StrEnum):
    """Why Leo uses a file."""

    FILE = "file"
    FOLDER = "folder"


class KnowledgeLimitError(ValueError):
    """Leo would use more bytes than the plan's knowledge limit."""


def leo_use(*, readable: bool, own: bool, folder: bool) -> LeoVia | None:
    """How Leo uses a file, or None when it does not."""
    if not readable:
        return None
    if own:
        return LeoVia.FILE
    return LeoVia.FOLDER if folder else None


def knowledge_limit(knowledge_base_mb: int | None) -> int | None:
    """The plan's knowledge limit in bytes; None is unlimited."""
    return None if knowledge_base_mb is None else knowledge_base_mb * MIB


def fits_knowledge(in_use_bytes: int, added_bytes: int, limit: int | None) -> bool:
    """Whether Leo may use `added_bytes` more on top of what it already uses."""
    return limit is None or in_use_bytes + added_bytes <= limit


@dataclass(frozen=True, slots=True)
class LeoCandidate:
    """A file as Leo's use sees it: its name and size, its own switch and its folder's."""

    file_id: UUID
    name: str
    size_bytes: int
    own: bool
    folder: bool

    @property
    def used(self) -> bool:
        """Whether Leo uses the file."""
        readable = leo_readable(self.name, self.size_bytes)
        return leo_use(readable=readable, own=self.own, folder=self.folder) is not None


def bytes_in_use(files: Iterable[LeoCandidate]) -> int:
    """The bytes Leo uses among `files`: only the files it can read and uses."""
    return sum(file.size_bytes for file in files if file.used)


@dataclass(frozen=True, slots=True)
class LeoShift:
    """What one change did to Leo's use: the files it started using, with their sizes, and
    the files it stopped using."""

    started: Mapping[UUID, int] = field(default_factory=dict)
    stopped: frozenset[UUID] = frozenset()

    @classmethod
    def of(cls, changes: Iterable[tuple[LeoCandidate, LeoCandidate]]) -> LeoShift:
        """The shift of (before, after) pairs of the same files."""
        started: dict[UUID, int] = {}
        stopped: set[UUID] = set()
        for before, after in changes:
            if after.used and not before.used:
                started[after.file_id] = after.size_bytes
            elif before.used and not after.used:
                stopped.add(after.file_id)
        return cls(started, frozenset(stopped))

    @property
    def empty(self) -> bool:
        """Whether nothing changed for Leo."""
        return not self.started and not self.stopped

    def check(self, in_use_after: int, limit: int | None) -> None:
        """Refuse a shift that starts using files while the bytes in use pass the limit.

        A shift that only stops using files is never refused, even over a lowered limit.
        """
        added = sum(self.started.values())
        if self.started and not fits_knowledge(in_use_after - added, added, limit):
            raise KnowledgeLimitError

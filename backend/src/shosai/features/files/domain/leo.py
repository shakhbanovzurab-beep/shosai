"""Whether Leo uses a file, and the knowledge limit (cabinet: `knowledge-base-api.md`).

Leo uses a file it can read when the file's own switch or its folder's is on, and says
which. The bytes of every file Leo uses count against the plan's `knowledge_base_mb`
(None: unlimited, 0: not included); a change that would pass it is refused.
"""

from enum import StrEnum
from typing import Final

MIB: Final = 1024**2


class LeoVia(StrEnum):
    """Why Leo uses a file."""

    FILE = "file"
    FOLDER = "folder"


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

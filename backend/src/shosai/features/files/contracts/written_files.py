"""Files another service wrote straight into a person's storage (files plan §3.2; meetings A7).

A recorder — LiveKit's egress for a call's video recording — writes the bytes itself, to the key
files gives it in the person's prefix (ADR 0055), so nothing is copied afterwards. When it is
done, the slice that asked adopts the object: it becomes the person's File Manager file under
the id it was written for, charged to their storage, and `files.file.uploaded` is published. A
repeated adoption answers the same file. Before asking for the bytes the slice reads how much
of the person's storage is left; a recording that ends over the limit is still the person's,
and files' quota rules act on it as on any other file.
"""

from dataclasses import dataclass
from typing import Final, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.homes import Home
from shosai.core.ports.keys import PortKey


@dataclass(frozen=True, slots=True)
class WrittenFile:
    """An object written at the key of `file_id`, to become the person's file."""

    file_id: UUID
    user_id: UUID
    name: str
    content_type: str
    size_bytes: int


class WrittenFiles(Protocol):
    """Keys for writers, and the adoption of what they wrote."""

    def key_for(self, user_id: UUID, file_id: UUID) -> str:
        """The key the writer puts the person's file at."""
        ...

    async def bytes_left(self, home: Home, user_id: UUID) -> int | None:
        """How much of the person's storage is free; None when it is unlimited."""
        ...

    async def adopt(self, session: AsyncSession, written: WrittenFile) -> UUID:
        """The written object as the person's File Manager file, in the caller's transaction
        of the person's home; the same file on a repeat."""
        ...


WRITTEN_FILES: Final = PortKey[WrittenFiles]("files.written_files")

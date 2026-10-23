"""Objects files holds for another slice (files plan §3.2, step 8c; ADR 0064).

A slice that keeps bytes for its rows — a task's attachments — holds them through files:
files keeps the object, its preview and the owner's storage; the slice keeps its row and
the held object's id. A held object comes from the person's ready upload of a holding
purpose or from a File Manager file they may read, sharing its object (FL-D4); the owner
is the transaction's person. An object goes only when no file row and no held object names
it. The holder checks who may read its row before it asks for a link.
"""

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.keys import PortKey
from shosai.features.files.domain.purposes import UploadPurpose
from shosai.features.workspaces.contracts import Viewer


@dataclass(frozen=True, slots=True)
class HeldObject:
    """An object files holds: its id and the facts its holder shows."""

    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    # Картинка, у которой files делает превью: PNG, JPEG, WebP или GIF по типу.
    image: bool


@dataclass(frozen=True, slots=True)
class ObjectLink:
    """A short-lived link to an object's bytes on Shosai's address (FL-D9)."""

    url: str
    expires_at: datetime


class HeldObjects(Protocol):
    """Holding, releasing and linking the objects of another slice's rows."""

    async def limit(self, home: Home, user_id: UUID) -> int | None:
        """The person's storage limit in bytes, read before the holder's transaction."""
        ...

    async def from_upload(
        self, session: AsyncSession, upload_id: UUID, purpose: UploadPurpose
    ) -> HeldObject:
        """The session's person's ready upload of a holding purpose, held; the same on a repeat.

        Raises `UploadNotClaimableError` for any other upload, `AppError`
        `storage_not_included` for a workspace's transaction until its storage opens.
        """
        ...

    async def from_file(
        self,
        session: AsyncSession,
        viewer: Viewer,
        file_id: UUID,
        hold: tuple[UploadPurpose, int | None],
    ) -> HeldObject:
        """A File Manager file the viewer may read, held on its object for the purpose and
        charged to the owner within the limit.

        Raises `FileUnreadableError`, or `AppError` `storage_limit` / `storage_not_included`.
        """
        ...

    async def release(self, session: AsyncSession, held_ids: Collection[UUID]) -> tuple[str, ...]:
        """Drop the held objects and free their bytes; the keys no one names any more, whose
        deletion is recorded and which `discard` deletes after the commit."""
        ...

    async def discard(self, home: Home, keys: Collection[str]) -> None:
        """Delete released objects from the bucket; a failure is retried by files' sweep."""
        ...

    async def links(
        self, scope: TenancyScope, held_ids: Collection[UUID]
    ) -> Mapping[UUID, ObjectLink]:
        """15-minute download links of the held objects that exist, signed after files' own
        short read in the scope, never inside the holder's transaction."""
        ...

    async def previews(self, scope: TenancyScope, held_ids: Collection[UUID]) -> Mapping[UUID, str]:
        """15-minute links of the previews made so far, signed like `links`; an object
        without one is absent."""
        ...

    async def prepare(self, home: Home, held_ids: Collection[UUID]) -> None:
        """Queue the previews of held images after the holder's commit; never raises."""
        ...


HELD_OBJECTS: Final = PortKey[HeldObjects]("files.held_objects")

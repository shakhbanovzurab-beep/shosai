"""A file's download link: through the edge, with the type pinned (FL-D9, ADR 0055 point 8).

Any file the viewer may read — their own or one shared with them — can be downloaded. The
link pins the stored type and opens inline only a type the browser cannot run; the edge
adds `nosniff` and a sandbox to the bytes. The link lives 15 minutes.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.ports.directory import PortDirectory
from shosai.core.storage.port import Disposition, ObjectStorage
from shosai.features.files.application.file_edits import file_gone
from shosai.features.files.application.visibility import visible_files
from shosai.features.files.domain.kinds import opens_inline
from shosai.features.files.infrastructure.download_links import edge_link
from shosai.features.files.infrastructure.file_records import StorageFileRecord
from shosai.features.identity.contracts import Principal
from shosai.features.workspaces.contracts import ACCESS_POLICY, Viewer


@dataclass(frozen=True, slots=True)
class DownloadLink:
    """Where the browser fetches the bytes, and until when."""

    url: str
    expires_at: datetime


class Downloads:
    """Links to the bytes of files a person may read."""

    def __init__(
        self,
        transactions: HomeTransactions,
        storage: tuple[Mapping[Home, ObjectStorage], PortDirectory],
        base: str | None,
    ) -> None:
        self._transactions = transactions
        self._objects, self._ports = storage
        self._base = base

    async def link(self, principal: Principal, file_id: UUID) -> DownloadLink:
        """A 15-minute link to a readable file."""
        query = visible_files(self._ports.get(ACCESS_POLICY), Viewer(principal.user_id)).where(
            StorageFileRecord.id == file_id
        )
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            record = await session.scalar(query)
        if record is None:
            raise file_gone()
        disposition = (
            Disposition.INLINE if opens_inline(record.content_type) else Disposition.ATTACHMENT
        )
        signed = await self._objects[principal.home].presign_get(
            record.object_key, filename=record.name, disposition=disposition,
            content_type=record.content_type,
        )  # fmt: skip
        return DownloadLink(edge_link(signed.url, principal.home, self._base), signed.expires_at)

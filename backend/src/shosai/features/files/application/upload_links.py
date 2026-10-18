"""What the client gets back about an upload: its state and a signed link per missing part.

A link is signed for one part's exact length and lives 15 minutes (§4.3); a client that
needs more time asks for the upload again and gets fresh links for the parts not done.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from shosai.core.kernel.homes import Home
from shosai.core.storage.port import (
    MultipartUpload,
    MultipartUploads,
    ObjectStorage,
    PresignedRequest,
)
from shosai.features.files.domain.purposes import UploadPurpose
from shosai.features.files.domain.uploads import UploadState, part_sizes
from shosai.features.files.infrastructure.upload_records import UploadRecord


@dataclass(frozen=True, slots=True)
class StorageOfHomes:
    """Each home's bucket: its objects and its multipart uploads."""

    objects: Mapping[Home, ObjectStorage]
    uploads: Mapping[Home, MultipartUploads]


@dataclass(frozen=True, slots=True)
class PartLink:
    """Where to PUT one part, and exactly how many bytes."""

    number: int
    size_bytes: int
    request: PresignedRequest


@dataclass(frozen=True, slots=True)
class UploadView:
    """An upload as its owner sees it."""

    id: UUID
    purpose: UploadPurpose
    state: UploadState
    filename: str
    content_type: str
    size_bytes: int
    expires_at: datetime
    done_parts: tuple[int, ...]
    links: tuple[PartLink, ...]


def view_of(record: UploadRecord, done: Sequence[int], links: Sequence[PartLink]) -> UploadView:
    """The owner's view of an upload row."""
    return UploadView(
        id=record.id, purpose=UploadPurpose(record.purpose), state=UploadState(record.state),
        filename=record.filename, content_type=record.content_type, size_bytes=record.size_bytes,
        expires_at=record.expires_at, done_parts=tuple(done), links=tuple(links),
    )  # fmt: skip


async def links_for(
    uploads: MultipartUploads, multipart: MultipartUpload, record: UploadRecord, done: Sequence[int]
) -> tuple[PartLink, ...]:
    """A signed link for each planned part not done yet."""
    finished = set(done)
    links = []
    for number, size in enumerate(part_sizes(record.size_bytes), start=1):
        if number in finished:
            continue
        request = await uploads.presign_part(multipart, number, content_length=size)
        links.append(PartLink(number, size, request))
    return tuple(links)

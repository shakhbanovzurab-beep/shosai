"""The ports of object storage: what a slice may ask of its home's bucket (ADR 0044).

Bytes live in the bucket of the home that holds the pointer — the full key — in its
database (inv-11); a slice takes `services.objects[home]` with the home of its scope.
Clients upload and download directly with presigned requests valid 15 minutes (§4.3), so
no API process carries the bytes; a server-side `put` is for what the server makes itself.
No database transaction is held across any of these calls (§14 rule 8).
"""

from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol

type PresignedMethod = Literal["GET", "PUT"]


class Disposition(StrEnum):
    """How a browser treats a downloaded object: save it, or show it in place."""

    ATTACHMENT = "attachment"
    INLINE = "inline"


@dataclass(frozen=True, slots=True)
class ObjectInfo:
    """What the bucket knows about an object; the content type is absent in listings."""

    key: str
    size: int
    etag: str
    last_modified: datetime
    content_type: str | None = None


@dataclass(frozen=True, slots=True)
class PresignedRequest:
    """A request a client sends to the bucket itself, with exactly these headers."""

    method: PresignedMethod
    url: str
    headers: Mapping[str, str]
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class MultipartUpload:
    """A multipart upload in progress: the object key and the bucket's upload id."""

    key: str
    upload_id: str


@dataclass(frozen=True, slots=True)
class UploadedPart:
    """A part the bucket has accepted; the ETag is its receipt."""

    number: int
    etag: str
    size: int


class ObjectStream(Protocol):
    """An object being read: what it is and its bytes, read as the caller consumes them."""

    @property
    def info(self) -> ObjectInfo:
        """The object's size, type and ETag, known before the first byte is read."""
        ...

    def chunks(self, size: int) -> AsyncIterator[bytes]:
        """The body in chunks of at most `size` bytes."""
        ...


class ObjectStorage(Protocol):
    """Objects of one home's bucket; slices receive one per home by injection."""

    async def put(self, key: str, body: bytes, *, content_type: str) -> ObjectInfo:
        """Store bytes the server made itself under `key`, replacing nothing else."""
        ...

    def open(self, key: str) -> AbstractAsyncContextManager[ObjectStream]:
        """Read an object as a stream; `ObjectNotFoundError` when it does not exist."""
        ...

    async def head(self, key: str) -> ObjectInfo | None:
        """The object's metadata, or None when it does not exist."""
        ...

    async def delete(self, key: str) -> None:
        """Delete an object; deleting a missing object succeeds."""
        ...

    async def delete_many(self, keys: Sequence[str]) -> None:
        """Delete objects in batches of 1000; `ObjectsNotDeletedError` names the ones left."""
        ...

    def list_objects(self, prefix: str) -> AsyncIterator[ObjectInfo]:
        """Every object under a prefix, in key order, page by page."""
        ...

    async def presign_get(
        self,
        key: str,
        *,
        filename: str,
        disposition: Disposition,
        content_type: str | None = None,
    ) -> PresignedRequest:
        """A download link; a given content type is pinned, whatever the object says."""
        ...

    async def presign_put(
        self, key: str, *, content_type: str, content_length: int
    ) -> PresignedRequest:
        """An upload link for exactly `content_length` bytes of `content_type`."""
        ...

    async def ping(self) -> None:
        """Raise when the bucket does not answer; the readiness probe calls it."""
        ...


class MultipartUploads(Protocol):
    """Resumable uploads of large objects by parts, each part sent by the client directly."""

    async def create(self, key: str, *, content_type: str) -> MultipartUpload:
        """Start an upload; the bucket's lifecycle rule removes it if it is abandoned."""
        ...

    async def presign_part(
        self, upload: MultipartUpload, number: int, *, content_length: int
    ) -> PresignedRequest:
        """An upload link for part `number` (1 to 10 000) of exactly `content_length` bytes."""
        ...

    async def list_parts(self, upload: MultipartUpload) -> list[UploadedPart]:
        """Parts the bucket has accepted, by number: where a resumed upload continues."""
        ...

    async def complete(self, upload: MultipartUpload, parts: Sequence[UploadedPart]) -> None:
        """Assemble the object from the parts; `StorageRejectedError` for a wrong list."""
        ...

    async def abort(self, upload: MultipartUpload) -> None:
        """Drop an upload and its parts; aborting a finished or unknown upload succeeds."""
        ...

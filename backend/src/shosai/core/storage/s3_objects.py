"""`ObjectStorage` over the one S3 bucket (ADR 0014).

The adapter may work under a root prefix of the bucket: keys given and returned are
relative to it, so a test run confined to `tests/slot-<N>/` cannot touch anything else.
Production works at the root of the bucket.
"""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final
from urllib.parse import quote

from aiobotocore.response import StreamingBody

from shosai.core.storage.errors import ObjectNotFoundError, ObjectsNotDeletedError
from shosai.core.storage.keys import check_object_key, check_prefix, check_root
from shosai.core.storage.port import Disposition, ObjectInfo, PresignedRequest
from shosai.core.storage.s3_client import S3Calls

if TYPE_CHECKING:
    from types_aiobotocore_s3 import S3Client
    from types_aiobotocore_s3.type_defs import ObjectIdentifierTypeDef

PRESIGN_TTL: Final = timedelta(minutes=15)
DELETE_BATCH: Final = 1000
LIST_PAGE: Final = 1000
# Запасное имя файла для старых браузеров — только безопасный ASCII; точное имя
# передаётся в filename* (RFC 6266, RFC 8187).
UNSAFE_FILENAME_CHARACTERS: Final = frozenset('"\\;')
FALLBACK_FILENAME: Final = "file"


def content_disposition(disposition: Disposition, filename: str) -> str:
    """`attachment; filename="report.pdf"; filename*=UTF-8''report.pdf` for any file name."""
    fallback = "".join(ascii_filename_character(character) for character in filename)
    encoded = quote(filename, safe="")
    return (
        f'{disposition.value}; filename="{fallback or FALLBACK_FILENAME}"; '
        f"filename*=UTF-8''{encoded}"
    )


def ascii_filename_character(character: str) -> str:
    """The character itself when an old browser reads it safely in quotes, otherwise `_`."""
    safe = (
        character.isascii()
        and character.isprintable()
        and character not in UNSAFE_FILENAME_CHARACTERS
    )
    return character if safe else "_"


class S3ObjectStream:
    """An object being read from the bucket; the connection returns to the pool on exit."""

    def __init__(self, info: ObjectInfo, body: StreamingBody) -> None:
        self._info = info
        self._body = body

    @property
    def info(self) -> ObjectInfo:
        """The object's size, type and ETag from the response headers."""
        return self._info

    async def chunks(self, size: int) -> AsyncIterator[bytes]:
        """The body in chunks of at most `size` bytes."""
        while chunk := await self._body.read(size):
            yield chunk


class S3ObjectStorage:
    """Objects of the bucket under an optional root prefix."""

    def __init__(self, client: S3Client, calls: S3Calls, root: str = "") -> None:
        self._client = client
        self._calls = calls
        self._bucket = calls.bucket
        self._root = check_root(root)

    async def put(self, key: str, body: bytes, *, content_type: str) -> ObjectInfo:
        """Store bytes the server made itself under `key`."""
        async with self._calls.call("PutObject"):
            reply = await self._client.put_object(
                Bucket=self._bucket, Key=self._full(key), Body=body, ContentType=content_type
            )
        return ObjectInfo(
            key=key,
            size=len(body),
            etag=reply["ETag"],
            last_modified=datetime.now(UTC),
            content_type=content_type,
        )

    @asynccontextmanager
    async def open(self, key: str) -> AsyncIterator[S3ObjectStream]:
        """Read an object as a stream; `ObjectNotFoundError` when it does not exist."""
        async with self._calls.call("GetObject"):
            reply = await self._client.get_object(Bucket=self._bucket, Key=self._full(key))
        info = ObjectInfo(
            key=key,
            size=reply["ContentLength"],
            etag=reply["ETag"],
            last_modified=reply["LastModified"],
            content_type=reply.get("ContentType"),
        )
        async with reply["Body"] as body:
            yield S3ObjectStream(info, body)

    async def head(self, key: str) -> ObjectInfo | None:
        """The object's metadata, or None when it does not exist."""
        try:
            async with self._calls.call("HeadObject"):
                reply = await self._client.head_object(Bucket=self._bucket, Key=self._full(key))
        except ObjectNotFoundError:
            return None
        return ObjectInfo(
            key=key,
            size=reply["ContentLength"],
            etag=reply["ETag"],
            last_modified=reply["LastModified"],
            content_type=reply.get("ContentType"),
        )

    async def delete(self, key: str) -> None:
        """Delete an object; deleting a missing object succeeds."""
        async with self._calls.call("DeleteObject"):
            await self._client.delete_object(Bucket=self._bucket, Key=self._full(key))

    async def delete_many(self, keys: Sequence[str]) -> None:
        """Delete objects in batches of 1000; `ObjectsNotDeletedError` names the ones left."""
        failed: list[str] = []
        codes: list[str] = []
        for start in range(0, len(keys), DELETE_BATCH):
            batch: list[ObjectIdentifierTypeDef] = [
                {"Key": self._full(key)} for key in keys[start : start + DELETE_BATCH]
            ]
            async with self._calls.call("DeleteObjects"):
                reply = await self._client.delete_objects(
                    Bucket=self._bucket, Delete={"Objects": batch, "Quiet": True}
                )
            for error in reply.get("Errors", []):
                failed.append(error.get("Key", "").removeprefix(self._root))
                codes.append(error.get("Code", ""))
        if failed:
            raise ObjectsNotDeletedError(failed, codes)

    async def list_objects(self, prefix: str) -> AsyncIterator[ObjectInfo]:
        """Every object under a prefix, in key order, one page of 1000 per request."""
        full_prefix = self._root + check_prefix(prefix)
        token: str | None = None
        while True:
            async with self._calls.call("ListObjectsV2"):
                if token is None:
                    page = await self._client.list_objects_v2(
                        Bucket=self._bucket, Prefix=full_prefix, MaxKeys=LIST_PAGE
                    )
                else:
                    page = await self._client.list_objects_v2(
                        Bucket=self._bucket,
                        Prefix=full_prefix,
                        MaxKeys=LIST_PAGE,
                        ContinuationToken=token,
                    )
            for item in page.get("Contents", []):
                yield ObjectInfo(
                    key=item["Key"].removeprefix(self._root),
                    size=item["Size"],
                    etag=item["ETag"],
                    last_modified=item["LastModified"],
                )
            token = page.get("NextContinuationToken")
            if not page.get("IsTruncated") or token is None:
                return

    async def presign_get(
        self,
        key: str,
        *,
        filename: str,
        disposition: Disposition,
        content_type: str | None = None,
    ) -> PresignedRequest:
        """A download link; a given content type is pinned, whatever the object says.

        Pinning matters for inline previews: the browser renders exactly the type named
        here, so an object holding HTML cannot run as a page on the bucket's origin.
        """
        params = {
            "Bucket": self._bucket,
            "Key": self._full(key),
            "ResponseContentDisposition": content_disposition(disposition, filename),
        }
        if content_type is not None:
            params["ResponseContentType"] = content_type
        expires_at = datetime.now(UTC) + PRESIGN_TTL
        url = await self._client.generate_presigned_url(
            "get_object", Params=params, ExpiresIn=int(PRESIGN_TTL.total_seconds())
        )
        return PresignedRequest(method="GET", url=url, headers={}, expires_at=expires_at)

    async def presign_put(
        self, key: str, *, content_type: str, content_length: int
    ) -> PresignedRequest:
        """An upload link for exactly `content_length` bytes of `content_type`."""
        expires_at = datetime.now(UTC) + PRESIGN_TTL
        url = await self._client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._bucket,
                "Key": self._full(key),
                "ContentType": content_type,
                "ContentLength": content_length,
            },
            ExpiresIn=int(PRESIGN_TTL.total_seconds()),
        )
        headers = {"Content-Type": content_type, "Content-Length": str(content_length)}
        return PresignedRequest(method="PUT", url=url, headers=headers, expires_at=expires_at)

    async def ping(self) -> None:
        """Raise `StorageUnavailableError` when the bucket does not answer."""
        async with self._calls.call("HeadBucket"):
            await self._client.head_bucket(Bucket=self._bucket)

    def _full(self, key: str) -> str:
        return self._root + check_object_key(key)

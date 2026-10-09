"""`MultipartUploads` over the one S3 bucket: resumable uploads sent by the client part by part.

The state of an upload lives in the bucket, not in a table: `list_parts` answers where a
resumed upload continues, because only the bucket knows for sure which parts it accepted
before a connection broke (draft lesson). Abandoned uploads are removed by the bucket's
lifecycle rule; `abort` removes one at once.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from shosai.core.storage.errors import ObjectNotFoundError
from shosai.core.storage.keys import check_object_key, check_root
from shosai.core.storage.port import MultipartUpload, PresignedRequest, UploadedPart
from shosai.core.storage.s3_client import S3Calls
from shosai.core.storage.s3_objects import PRESIGN_TTL

if TYPE_CHECKING:
    from types_aiobotocore_s3 import S3Client

FIRST_PART: Final = 1
LAST_PART: Final = 10_000


def check_part_number(number: int) -> int:
    """S3 numbers parts from 1 to 10 000."""
    if not FIRST_PART <= number <= LAST_PART:
        message = f"номер части — от {FIRST_PART} до {LAST_PART}"
        raise ValueError(message)
    return number


class S3MultipartUploads:
    """Multipart uploads to the bucket under the same root prefix as its objects."""

    def __init__(self, client: S3Client, calls: S3Calls, root: str = "") -> None:
        self._client = client
        self._calls = calls
        self._bucket = calls.bucket
        self._root = check_root(root)

    async def create(self, key: str, *, content_type: str) -> MultipartUpload:
        """Start an upload of `key`."""
        async with self._calls.call("CreateMultipartUpload"):
            reply = await self._client.create_multipart_upload(
                Bucket=self._bucket, Key=self._full(key), ContentType=content_type
            )
        return MultipartUpload(key=key, upload_id=reply["UploadId"])

    async def presign_part(
        self, upload: MultipartUpload, number: int, *, content_length: int
    ) -> PresignedRequest:
        """An upload link for part `number` of exactly `content_length` bytes."""
        expires_at = datetime.now(UTC) + PRESIGN_TTL
        url = await self._client.generate_presigned_url(
            "upload_part",
            Params={
                "Bucket": self._bucket,
                "Key": self._full(upload.key),
                "UploadId": upload.upload_id,
                "PartNumber": check_part_number(number),
                "ContentLength": content_length,
            },
            ExpiresIn=int(PRESIGN_TTL.total_seconds()),
        )
        headers = {"Content-Length": str(content_length)}
        return PresignedRequest(method="PUT", url=url, headers=headers, expires_at=expires_at)

    async def list_parts(self, upload: MultipartUpload) -> list[UploadedPart]:
        """Parts the bucket has accepted, by number; `ObjectNotFoundError` for no such upload."""
        parts: list[UploadedPart] = []
        marker = 0
        while True:
            async with self._calls.call("ListParts"):
                page = await self._client.list_parts(
                    Bucket=self._bucket,
                    Key=self._full(upload.key),
                    UploadId=upload.upload_id,
                    PartNumberMarker=marker,
                )
            parts.extend(
                UploadedPart(number=part["PartNumber"], etag=part["ETag"], size=part["Size"])
                for part in page.get("Parts", [])
            )
            if not page.get("IsTruncated"):
                return sorted(parts, key=lambda part: part.number)
            marker = page.get("NextPartNumberMarker", 0)

    async def complete(self, upload: MultipartUpload, parts: Sequence[UploadedPart]) -> None:
        """Assemble the object; `StorageRejectedError` for a wrong or too small part."""
        async with self._calls.call("CompleteMultipartUpload"):
            await self._client.complete_multipart_upload(
                Bucket=self._bucket,
                Key=self._full(upload.key),
                UploadId=upload.upload_id,
                MultipartUpload={
                    "Parts": [
                        {"PartNumber": part.number, "ETag": part.etag}
                        for part in sorted(parts, key=lambda part: part.number)
                    ]
                },
            )

    async def abort(self, upload: MultipartUpload) -> None:
        """Drop an upload and its parts; an unknown or finished upload is already gone."""
        try:
            async with self._calls.call("AbortMultipartUpload"):
                await self._client.abort_multipart_upload(
                    Bucket=self._bucket, Key=self._full(upload.key), UploadId=upload.upload_id
                )
        except ObjectNotFoundError:
            return

    def _full(self, key: str) -> str:
        return self._root + check_object_key(key)

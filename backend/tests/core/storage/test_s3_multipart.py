"""Multipart uploads sent part by part with presigned requests: resume, complete, abort."""

import httpx
import pytest

from tests.core.storage.adapters import SlotStorage, slot_storage
from tests.harness.shared_services import SlotBucket
from whisperer.core.storage.errors import ObjectNotFoundError, StorageRejectedError
from whisperer.core.storage.port import MultipartUpload, UploadedPart
from whisperer.core.storage.s3_multipart import check_part_number

RECORDING = "u-7/meetings/m-1/audio.webm"
# S3 принимает части от 5 МиБ, кроме последней.
FIRST_PART = bytes(range(256)) * (5 * 1024 * 4)
LAST_PART = b"tail of the recording"


async def send_part(
    storage: SlotStorage, upload: MultipartUpload, number: int, body: bytes
) -> httpx.Response:
    """What a client does: ask for a signed request and send the part to the bucket itself."""
    request = await storage.uploads.presign_part(upload, number, content_length=len(body))
    async with httpx.AsyncClient() as http:
        return await http.put(request.url, content=body, headers=dict(request.headers))


async def test_an_upload_resumes_from_the_parts_the_bucket_accepted(bucket: SlotBucket) -> None:
    storage = slot_storage(bucket)
    upload = await storage.uploads.create(RECORDING, content_type="audio/webm")

    assert (await send_part(storage, upload, 1, FIRST_PART)).status_code == 200
    accepted = await storage.uploads.list_parts(upload)
    assert [(part.number, part.size) for part in accepted] == [(1, len(FIRST_PART))]

    assert (await send_part(storage, upload, 2, LAST_PART)).status_code == 200
    await storage.uploads.complete(upload, await storage.uploads.list_parts(upload))

    async with storage.objects.open(RECORDING) as stream:
        stored = b"".join([chunk async for chunk in stream.chunks(1 << 20)])
    assert stored == FIRST_PART + LAST_PART
    assert stream.info.content_type == "audio/webm"


async def test_an_aborted_upload_is_gone_and_aborting_again_succeeds(bucket: SlotBucket) -> None:
    storage = slot_storage(bucket)
    upload = await storage.uploads.create(RECORDING, content_type="audio/webm")
    await send_part(storage, upload, 1, LAST_PART)

    await storage.uploads.abort(upload)
    await storage.uploads.abort(upload)

    with pytest.raises(ObjectNotFoundError):
        await storage.uploads.list_parts(upload)
    assert await storage.objects.head(RECORDING) is None


async def test_a_wrong_part_list_is_refused(bucket: SlotBucket) -> None:
    storage = slot_storage(bucket)
    upload = await storage.uploads.create(RECORDING, content_type="audio/webm")
    await send_part(storage, upload, 1, LAST_PART)

    with pytest.raises(StorageRejectedError) as raised:
        await storage.uploads.complete(upload, [UploadedPart(number=1, etag='"0"', size=1)])

    assert raised.value.code
    assert storage.requests("CompleteMultipartUpload", "rejected") == 1
    await storage.uploads.abort(upload)


async def test_a_part_sent_with_another_length_is_refused(bucket: SlotBucket) -> None:
    storage = slot_storage(bucket)
    upload = await storage.uploads.create(RECORDING, content_type="audio/webm")
    request = await storage.uploads.presign_part(upload, 1, content_length=len(LAST_PART))

    async with httpx.AsyncClient() as http:
        response = await http.put(request.url, content=LAST_PART + b"!")

    assert response.status_code == 403
    assert await storage.uploads.list_parts(upload) == []
    await storage.uploads.abort(upload)


@pytest.mark.parametrize("number", [0, -1, 10_001])
def test_parts_are_numbered_from_1_to_10000(number: int) -> None:
    with pytest.raises(ValueError, match="номер части"):
        check_part_number(number)

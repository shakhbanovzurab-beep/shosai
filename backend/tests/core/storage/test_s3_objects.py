"""Objects of the one bucket: stored, streamed, listed, deleted and signed, under a root."""

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from tests.core.storage.adapters import slot_storage
from tests.harness.shared_services import SlotBucket
from whisperer.core.storage.errors import ObjectNotFoundError
from whisperer.core.storage.port import Disposition
from whisperer.core.storage.s3_objects import content_disposition

REPORT = "u-7/files/report.pdf"
BODY = b"%PDF-1.7 " + bytes(range(256)) * 64


async def test_an_object_is_stored_streamed_and_described(bucket: SlotBucket) -> None:
    storage = slot_storage(bucket)

    stored = await storage.objects.put(REPORT, BODY, content_type="application/pdf")
    head = await storage.objects.head(REPORT)
    async with storage.objects.open(REPORT) as stream:
        chunks = [chunk async for chunk in stream.chunks(4096)]

    assert head is not None
    assert (head.size, head.etag, head.content_type) == (len(BODY), stored.etag, "application/pdf")
    assert stream.info.size == len(BODY)
    assert b"".join(chunks) == BODY
    assert max(len(chunk) for chunk in chunks) <= 4096
    # Объект лежит под корнем прогона, а снаружи корня ничего не появилось.
    raw = await bucket.client.head_object(Bucket=bucket.bucket, Key=bucket.root + REPORT)
    assert raw["ContentLength"] == len(BODY)


async def test_a_missing_object_is_none_or_not_found(bucket: SlotBucket) -> None:
    storage = slot_storage(bucket)

    assert await storage.objects.head("u-7/files/none.pdf") is None
    with pytest.raises(ObjectNotFoundError):
        async with storage.objects.open("u-7/files/none.pdf"):
            pytest.fail("отсутствующий объект не открывается")

    assert storage.requests("HeadObject", "not_found") == 1
    assert storage.requests("GetObject", "not_found") == 1


async def test_listing_returns_keys_relative_to_the_root_in_order(bucket: SlotBucket) -> None:
    storage = slot_storage(bucket)
    for name in ("b.txt", "a.txt", "c/d.txt"):
        await storage.objects.put(f"u-7/{name}", b"x", content_type="text/plain")
    await storage.objects.put("u-8/a.txt", b"x", content_type="text/plain")

    listed = [info.key async for info in storage.objects.list_objects("u-7/")]

    assert listed == ["u-7/a.txt", "u-7/b.txt", "u-7/c/d.txt"]


async def test_deletion_is_idempotent_and_batched(bucket: SlotBucket) -> None:
    storage = slot_storage(bucket)
    keys = [f"u-7/batch/{index}.bin" for index in range(5)]
    for key in keys:
        await storage.objects.put(key, b"x", content_type="application/octet-stream")

    await storage.objects.delete(keys[0])
    await storage.objects.delete(keys[0])
    await storage.objects.delete_many(keys)
    await storage.objects.delete_many([])

    assert [info.key async for info in storage.objects.list_objects("u-7/")] == []
    assert storage.requests("DeleteObjects", "ok") == 1


async def test_a_presigned_download_pins_the_type_and_names_the_file(bucket: SlotBucket) -> None:
    storage = slot_storage(bucket)
    await storage.objects.put(REPORT, b"<script>alert(1)</script>", content_type="text/html")

    link = await storage.objects.presign_get(
        REPORT, filename='Отчёт "Q3".pdf', disposition=Disposition.INLINE, content_type="text/plain"
    )
    async with httpx.AsyncClient() as http:
        response = await http.get(link.url)

    assert response.status_code == 200
    assert response.content == b"<script>alert(1)</script>"
    assert response.headers["Content-Type"].startswith("text/plain")
    assert response.headers["Content-Disposition"] == (
        'inline; filename="_____ _Q3_.pdf"; '
        "filename*=UTF-8''%D0%9E%D1%82%D1%87%D1%91%D1%82%20%22Q3%22.pdf"
    )
    assert link.method == "GET"
    assert parse_qs(urlsplit(link.url).query)["X-Amz-Expires"] == ["900"]
    assert link.expires_at - datetime.now(UTC) <= timedelta(minutes=15)


async def test_a_download_without_a_pinned_type_keeps_the_stored_one(bucket: SlotBucket) -> None:
    storage = slot_storage(bucket)
    await storage.objects.put(REPORT, BODY, content_type="application/pdf")

    link = await storage.objects.presign_get(
        REPORT, filename="report.pdf", disposition=Disposition.ATTACHMENT
    )
    async with httpx.AsyncClient() as http:
        response = await http.get(link.url)

    assert response.content == BODY
    assert response.headers["Content-Type"] == "application/pdf"
    assert response.headers["Content-Disposition"].startswith("attachment; ")


async def test_a_presigned_upload_takes_exactly_the_signed_object(bucket: SlotBucket) -> None:
    storage = slot_storage(bucket)
    body = b"0123456789"
    link = await storage.objects.presign_put(
        REPORT, content_type="application/pdf", content_length=10
    )

    async with httpx.AsyncClient() as http:
        longer = await http.put(
            link.url, content=body + b"!", headers={"Content-Type": "application/pdf"}
        )
        retyped = await http.put(link.url, content=body, headers={"Content-Type": "text/html"})
        exact = await http.put(link.url, content=body, headers=dict(link.headers))

    assert (longer.status_code, retyped.status_code) == (403, 403)
    assert exact.status_code == 200
    head = await storage.objects.head(REPORT)
    assert head is not None
    assert (head.size, head.content_type) == (10, "application/pdf")


async def test_the_bucket_answers_the_probe(bucket: SlotBucket) -> None:
    storage = slot_storage(bucket)

    await storage.objects.ping()

    assert storage.requests("HeadBucket", "ok") == 1


@pytest.mark.parametrize(
    ("disposition", "filename", "header"),
    [
        (
            Disposition.ATTACHMENT,
            "report.pdf",
            "attachment; filename=\"report.pdf\"; filename*=UTF-8''report.pdf",
        ),
        (
            Disposition.INLINE,
            "a;b\\c.txt",
            "inline; filename=\"a_b_c.txt\"; filename*=UTF-8''a%3Bb%5Cc.txt",
        ),
        (Disposition.ATTACHMENT, "", "attachment; filename=\"file\"; filename*=UTF-8''"),
    ],
)
def test_content_disposition_carries_a_safe_and_an_exact_name(
    disposition: Disposition, filename: str, header: str
) -> None:
    assert content_disposition(disposition, filename) == header

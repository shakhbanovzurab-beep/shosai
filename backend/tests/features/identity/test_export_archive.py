"""The export ZIP goes to the bucket part by part, and a failed one leaves no object."""

import io
import os
import zipfile
from collections.abc import AsyncIterator

import pytest

from shosai.features.identity.infrastructure.export_archive import (
    PART_SIZE,
    ArchiveEntry,
    write_archive,
)
from tests.core.storage.adapters import slot_storage
from tests.harness.shared_services import SlotBucket

KEY = "exports/u-1/job-1.zip"
# Случайные байты не сжимаются: архив больше одной части.
LARGE = os.urandom(PART_SIZE + PART_SIZE // 2)


async def chunks_of(data: bytes, size: int = 1 << 20) -> AsyncIterator[bytes]:
    for start in range(0, len(data), size):
        yield data[start : start + size]


async def entries(*files: tuple[str, bytes]) -> AsyncIterator[ArchiveEntry]:
    for name, data in files:
        yield name, chunks_of(data)


async def test_a_large_archive_is_sent_in_parts_and_reads_back_whole(bucket: SlotBucket) -> None:
    storage = slot_storage(bucket)

    size = await write_archive(
        storage.uploads, KEY, entries(("core/big.bin", LARGE), ("identity/users.jsonl", b"{}\n"))
    )

    async with storage.objects.open(KEY) as stream:
        stored = b"".join([chunk async for chunk in stream.chunks(1 << 20)])
    archive = zipfile.ZipFile(io.BytesIO(stored))
    assert size == len(stored) > PART_SIZE
    assert archive.read("core/big.bin") == LARGE
    assert archive.read("identity/users.jsonl") == b"{}\n"


async def test_an_archive_whose_source_fails_leaves_no_object(bucket: SlotBucket) -> None:
    storage = slot_storage(bucket)

    async def broken() -> AsyncIterator[ArchiveEntry]:
        yield "core/big.bin", chunks_of(LARGE)
        message = "база дома не ответила"
        raise ConnectionError(message)

    with pytest.raises(ConnectionError):
        await write_archive(storage.uploads, KEY, broken())

    assert await storage.objects.head(KEY) is None

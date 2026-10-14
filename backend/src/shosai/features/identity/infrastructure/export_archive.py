"""Writing the export archive into the home's bucket, a ZIP sent part by part (§3.6).

The ZIP is written to a buffer that never holds more than one part and a chunk: every
full 8 MiB goes to the bucket as a part of a multipart upload, the rest with the last
part. Compression runs in a worker thread, so a large file never holds the event loop.
An upload that does not complete is aborted; the bucket's lifecycle rule removes any part
an abort could not reach.
"""

import asyncio
import io
import zipfile
from collections.abc import AsyncIterator, Buffer
from typing import Final

from shosai.core.storage.port import MultipartUpload, MultipartUploads, UploadedPart
from shosai.features.identity.domain.export import ARCHIVE_TYPE

# S3 принимает части от 5 МиБ, кроме последней; 8 МиБ — с запасом и без лишних запросов.
PART_SIZE: Final = 8 * 1024 * 1024

type ArchiveEntry = tuple[str, AsyncIterator[bytes]]


class _PartBuffer(io.RawIOBase):
    """A write-only, unseekable stream whose bytes leave in whole parts."""

    def __init__(self) -> None:
        super().__init__()
        self._pending = bytearray()

    def writable(self) -> bool:
        """The ZIP writes here."""
        return True

    def write(self, data: Buffer, /) -> int:
        """Keep the bytes until they make a part."""
        view = memoryview(data)
        self._pending += view
        return view.nbytes

    def parts(self, *, final: bool) -> list[bytes]:
        """Every full part, and the remainder too when the archive is complete."""
        ready = []
        while len(self._pending) >= PART_SIZE:
            ready.append(bytes(self._pending[:PART_SIZE]))
            del self._pending[:PART_SIZE]
        if final and (self._pending or not ready):
            ready.append(bytes(self._pending))
            self._pending.clear()
        return ready


async def write_archive(
    uploads: MultipartUploads, key: str, entries: AsyncIterator[ArchiveEntry]
) -> int:
    """Write the entries as one ZIP under `key`; the archive's size in bytes."""
    upload = await uploads.create(key, content_type=ARCHIVE_TYPE)
    buffer = _PartBuffer()
    sent: list[UploadedPart] = []
    completed = False
    try:
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            async for path, chunks in entries:
                with archive.open(path, "w", force_zip64=True) as entry:
                    async for chunk in chunks:
                        await asyncio.to_thread(entry.write, chunk)
                        sent += await _send(uploads, upload, buffer.parts(final=False), sent)
        sent += await _send(uploads, upload, buffer.parts(final=True), sent)
        await uploads.complete(upload, sent)
        completed = True
    finally:
        if not completed:
            await uploads.abort(upload)
    return sum(part.size for part in sent)


async def _send(
    uploads: MultipartUploads,
    upload: MultipartUpload,
    bodies: list[bytes],
    sent: list[UploadedPart],
) -> list[UploadedPart]:
    first = len(sent) + 1
    return [
        await uploads.upload_part(upload, number, body)
        for number, body in enumerate(bodies, start=first)
    ]

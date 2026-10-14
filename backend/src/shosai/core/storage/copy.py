"""Copying objects between the buckets of two homes under the same keys (ADR 0044, §6).

An account transfer copies the account's objects before it switches the pointers, so a
pointer row moved to the other home finds its bytes there under the same key. Each object
streams through in parts of 8 MiB; it never sits whole in memory. A copy repeated after a
failure writes the same bytes again.
"""

from typing import Final

from shosai.core.storage.port import MultipartUploads, ObjectStorage, UploadedPart

PART_SIZE: Final = 8 * 1024 * 1024
READ_CHUNK: Final = 1 << 20
DEFAULT_TYPE: Final = "application/octet-stream"


async def copy_objects(source: ObjectStorage, target: MultipartUploads, prefix: str) -> int:
    """Copy every object under `prefix` to the target bucket; how many were copied."""
    copied = 0
    async for item in source.list_objects(prefix):
        await copy_object(source, target, item.key)
        copied += 1
    return copied


async def copy_object(source: ObjectStorage, target: MultipartUploads, key: str) -> None:
    """Stream one object to the target bucket under the same key."""
    uploads = target
    async with source.open(key) as stream:
        content_type = stream.info.content_type or DEFAULT_TYPE
        upload = await uploads.create(key, content_type=content_type)
        parts: list[UploadedPart] = []
        pending = bytearray()
        completed = False
        try:
            async for chunk in stream.chunks(READ_CHUNK):
                pending += chunk
                while len(pending) >= PART_SIZE:
                    body = bytes(pending[:PART_SIZE])
                    del pending[:PART_SIZE]
                    parts.append(await uploads.upload_part(upload, len(parts) + 1, body))
            if pending or not parts:
                parts.append(await uploads.upload_part(upload, len(parts) + 1, bytes(pending)))
            await uploads.complete(upload, parts)
            completed = True
        finally:
            if not completed:
                await uploads.abort(upload)

"""A stage's scratch directory: the recording fetched there, everything removed after it (MT-D10).

The tools read and write local files only, so a stage fetches the run's object from its
home's bucket into a fresh temporary directory, streamed in chunks, and the directory with
every part cut in it is removed when the stage leaves it, whatever its end.
"""

import asyncio
import tempfile
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Final

from shosai.core.kernel.homes import Home
from shosai.core.storage.port import ObjectStorage

CHUNK: Final = 1024 * 1024


@asynccontextmanager
async def scratch() -> AsyncIterator[Path]:
    """A fresh directory, removed with everything in it afterwards."""
    with tempfile.TemporaryDirectory(prefix="shosai-recording-") as directory:
        yield Path(directory)


async def fetched(
    storage: Mapping[Home, ObjectStorage], home: Home, key: str, directory: Path
) -> Path:
    """The object written to the directory, read from the bucket in chunks.

    The disk is written off the event loop, a chunk at a time.
    """
    target = directory / "recording"
    async with storage[home].open(key) as stream:
        file = await asyncio.to_thread(target.open, "wb")
        try:
            async for chunk in stream.chunks(CHUNK):
                await asyncio.to_thread(file.write, chunk)
        finally:
            await asyncio.to_thread(file.close)
    return target

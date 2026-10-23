"""Which held objects get a preview and what it is (ADR 0064 point 5; KG-D3).

A PNG, JPEG, WebP or GIF — the types the cabinet shows as images — gets a WebP preview at
most 640 px wide, from a source of at most 25 MiB and 40 megapixels: anything larger is
not decoded, so a crafted image cannot exhaust a worker.
"""

from typing import Final

IMAGE_TYPES: Final = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})
PREVIEW_TYPE: Final = "image/webp"
PREVIEW_WIDTH: Final = 640
# Высота превью ограничена, чтобы длинный скриншот не стал многомегабайтной лентой.
PREVIEW_HEIGHT: Final = 1920
SOURCE_MAX_BYTES: Final = 25 * 1024**2
SOURCE_MAX_PIXELS: Final = 40_000_000


def previewable(content_type: str) -> bool:
    """Whether an object of this type is an image files previews."""
    return content_type in IMAGE_TYPES

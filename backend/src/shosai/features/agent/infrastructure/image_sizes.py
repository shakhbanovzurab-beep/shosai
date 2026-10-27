"""A drawn picture's size, read from its header with Pillow: no pixel is decoded.

The type the bytes really are must be the one the model named; a picture past the pixel cap,
or anything Pillow cannot read, is refused.
"""

from io import BytesIO
from typing import Final

from PIL import Image, UnidentifiedImageError

from shosai.features.agent.domain.images import PIXELS_MAX

FORMATS: Final = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}


class ImageRefusedError(Exception):
    """The bytes are not a picture of their type within the caps."""


def image_size(data: bytes, content_type: str) -> tuple[int, int]:
    """The picture's width and height."""
    try:
        with Image.open(BytesIO(data)) as image:
            width, height = image.size
            kind = FORMATS.get(image.format or "")
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as error:
        raise ImageRefusedError from error
    if kind != content_type or width < 1 or height < 1 or width * height > PIXELS_MAX:
        raise ImageRefusedError
    return width, height

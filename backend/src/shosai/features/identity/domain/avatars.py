"""Avatar rules: the bytes decide the type, never the name or the header (ADR 0045 point 8).

The draft trusted the client's `Content-Type` and kept the image as a data URL in the
account row. Here the first bytes must be a PNG, JPEG or WebP signature, the header
must give dimensions within 16 to 1024 pixels a side, and the whole file is at most
1 MiB; anything else, a script named `.png` included, is refused before it is stored.
"""

import struct
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

MAX_AVATAR_BYTES: Final = 1024 * 1024
MIN_SIDE: Final = 16
MAX_SIDE: Final = 1024
PNG_SIGNATURE: Final = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE: Final = b"\xff\xd8\xff"
# Маркеры JPEG с размерами кадра: SOF0…SOF15, кроме DHT (C4), JPG (C8) и DAC (CC).
JPEG_FRAMES: Final = frozenset(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}
JPEG_MARKER: Final = 0xFF
# Где кончаются заголовки с размерами: IHDR у PNG, кадр VP8, VP8L и VP8X у WebP.
PNG_HEADER: Final = 24
VP8_HEADER: Final = 30
VP8L_HEADER: Final = 25


class AvatarFormat(StrEnum):
    """The image types an avatar may be, by their media type."""

    PNG = "image/png"
    JPEG = "image/jpeg"
    WEBP = "image/webp"

    @property
    def extension(self) -> str:
        """The object key's extension."""
        return {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[self.value]


class AvatarProblem(StrEnum):
    """Why an avatar is refused; the value is the client's error code."""

    TOO_LARGE = "avatar_too_large"
    NOT_AN_IMAGE = "avatar_type"
    BAD_SIZE = "avatar_dimensions"


@dataclass(frozen=True, slots=True)
class AvatarCheck:
    """The image's type, or why it is refused."""

    format: AvatarFormat | None
    problem: AvatarProblem | None


def check_avatar(data: bytes) -> AvatarCheck:
    """The avatar's type when its bytes are an acceptable image."""
    if len(data) > MAX_AVATAR_BYTES:
        return AvatarCheck(None, AvatarProblem.TOO_LARGE)
    found = _sniff(data)
    if found is None:
        return AvatarCheck(None, AvatarProblem.NOT_AN_IMAGE)
    image_format, size = found
    if size is None or not all(MIN_SIDE <= side <= MAX_SIDE for side in size):
        return AvatarCheck(None, AvatarProblem.BAD_SIZE)
    return AvatarCheck(image_format, None)


def _sniff(data: bytes) -> tuple[AvatarFormat, tuple[int, int] | None] | None:
    if data.startswith(PNG_SIGNATURE):
        return AvatarFormat.PNG, _png_size(data)
    if data.startswith(JPEG_SIGNATURE):
        return AvatarFormat.JPEG, _jpeg_size(data)
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return AvatarFormat.WEBP, _webp_size(data)
    return None


def _png_size(data: bytes) -> tuple[int, int] | None:
    if len(data) < PNG_HEADER or data[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def _jpeg_size(data: bytes) -> tuple[int, int] | None:
    position = 2
    while position + 9 < len(data):
        if data[position] != JPEG_MARKER:
            return None
        marker = data[position + 1]
        length = struct.unpack(">H", data[position + 2 : position + 4])[0]
        if marker in JPEG_FRAMES:
            height, width = struct.unpack(">HH", data[position + 5 : position + 9])
            return width, height
        position += 2 + length
    return None


def _webp_size(data: bytes) -> tuple[int, int] | None:
    chunk = data[12:16]
    if chunk == b"VP8 " and len(data) >= VP8_HEADER:
        width, height = struct.unpack("<HH", data[26:30])
        return width & 0x3FFF, height & 0x3FFF
    if chunk == b"VP8L" and len(data) >= VP8L_HEADER:
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if chunk == b"VP8X" and len(data) >= VP8_HEADER:
        return int.from_bytes(data[24:27], "little") + 1, int.from_bytes(data[27:30], "little") + 1
    return None

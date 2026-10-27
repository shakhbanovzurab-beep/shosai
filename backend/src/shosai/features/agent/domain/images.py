"""Pictures Leo draws for the platform operator (AG-D5, AG-D10; agent step 16b2).

A picture is a platform object in the EU home's bucket under `platform/agent/images/` (ADR
0055), never a person's: only the operator's Leo draws one. The answer keeps it by reference,
with its size so the panel holds its place before it loads; the bytes are read through a
short-lived link. A picture goes with the thread of the run that drew it.
"""

from typing import Final
from uuid import UUID

PROMPT_MAX: Final = 2_000
CAPTION_MAX: Final = 200
# Что модель картинок может вернуть и сколько: больше — не картинка для панели.
IMAGE_TYPES: Final = frozenset({"image/png", "image/jpeg", "image/webp"})
BYTES_MAX: Final = 10 * 1024 * 1024
PIXELS_MAX: Final = 40_000_000
KEY_PREFIX: Final = "platform/agent/images/"


def image_key(image_id: UUID) -> str:
    """The picture's key in the EU home's bucket."""
    return f"{KEY_PREFIX}{image_id}"


def extension_of(content_type: str) -> str:
    """The file extension of a picture's type, for the link's file name."""
    return content_type.split("/", 1)[1]

"""A held image's WebP preview, made with Pillow (ADR 0064 point 5).

Decoding is CPU work: the caller runs it in a thread. The image's size is read from its
header before any pixel is decoded, and an image past the pixel cap is refused, as is
anything Pillow cannot read; the first frame of an animation is the preview, turned as its
EXIF says.
"""

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from shosai.features.files.domain.previews import (
    PREVIEW_HEIGHT,
    PREVIEW_WIDTH,
    SOURCE_MAX_PIXELS,
)

WEBP_QUALITY = 80


class PreviewRefusedError(Exception):
    """The bytes are not an image Pillow reads within the caps."""


def webp_preview(source: bytes) -> bytes:
    """The WebP preview of an image, at most 640 px wide."""
    try:
        with Image.open(BytesIO(source)) as image:
            width, height = image.size
            if width * height > SOURCE_MAX_PIXELS:
                raise PreviewRefusedError
            image.seek(0)
            turned = ImageOps.exif_transpose(image)
            mode = "RGBA" if "A" in turned.getbands() or "transparency" in turned.info else "RGB"
            frame = turned.convert(mode)
            frame.thumbnail((PREVIEW_WIDTH, PREVIEW_HEIGHT), Image.Resampling.LANCZOS)
            out = BytesIO()
            frame.save(out, format="WEBP", quality=WEBP_QUALITY, method=4)
            return out.getvalue()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as error:
        raise PreviewRefusedError from error

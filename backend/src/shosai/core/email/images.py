"""The images mail points at, served from a fixed list (F6 plan §3.8).

`shosai-icon.png` is the layout's logo, rendered from `docs/brand/shosai-icon.svg` at four
times its 36 px size. `apple.png`, `windows.png` and `hazard.png` are the draft layout's,
kept byte for byte for mail already sent. A name outside the list is unknown: no path is
ever built from a request. Files are read once at start; the ETag is their content hash.
"""

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files  # nosemgrep
from types import MappingProxyType
from typing import Final

IMAGE_NAMES: Final = ("shosai-icon.png", "apple.png", "windows.png", "hazard.png")
# Имена без версии: месяц кэша, а не immutable, чтобы замена картинки дошла до клиентов.
IMAGE_CACHE: Final = "public, max-age=2592000"


@dataclass(frozen=True, slots=True)
class EmailImage:
    """One image: its bytes and their tag."""

    content: bytes
    etag: str


def load_email_images() -> Mapping[str, EmailImage]:
    """Every listed image from the package."""
    assets = files("shosai.core.email").joinpath("assets")
    images: dict[str, EmailImage] = {}
    for name in IMAGE_NAMES:
        content = assets.joinpath(name).read_bytes()
        etag = f'"{hashlib.sha256(content).hexdigest()[:32]}"'
        images[name] = EmailImage(content, etag)
    return MappingProxyType(images)

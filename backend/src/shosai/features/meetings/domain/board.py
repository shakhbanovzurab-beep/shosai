"""The room's board as the server keeps it (MR-D13, meetings plan §3.5).

One scene per room, as the editor saved it: the server counts and measures its elements and
images and never reads them. A save names the version it was made on; a save made on another
version is stale, and its client loads the latest before it saves again. The board's picture
is a PNG a participant uploads into the owner's storage under one id per call, replaced while
the call goes on and filed in File Manager when the call ends.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Final

ELEMENTS_MAX: Final = 20_000
ELEMENTS_BYTES: Final = 4 * 1024 * 1024
FILES_BYTES: Final = 8 * 1024 * 1024
# PNG доски с картинками до 8 МиБ на стороне до 4096 px — с запасом (агентское решение).
PICTURE_BYTES_MAX: Final = 25 * 1024 * 1024
PICTURE_TYPE: Final = "image/png"
# Сохраняет один участник, не чаще раза в 2,5 с; картинка — через 30 с после правки и при уходе.
SAVES_PER_MINUTE: Final = 30
PICTURES_PER_MINUTE: Final = 6


@dataclass(frozen=True, slots=True)
class SceneSize:
    """What a save weighs: how many elements, and their JSON and its images' JSON in bytes."""

    elements: int
    elements_bytes: int
    files_bytes: int


def fits(size: SceneSize) -> bool:
    """Whether a scene keeps within the board's limits."""
    return (
        size.elements <= ELEMENTS_MAX
        and size.elements_bytes <= ELEMENTS_BYTES
        and size.files_bytes <= FILES_BYTES
    )


def picture_name(title: str | None, started_at: datetime) -> str:
    """The picture's name in File Manager, beside the call's recording."""
    return f"{title or 'Meeting'} {started_at:%Y-%m-%d %H-%M} board.png"

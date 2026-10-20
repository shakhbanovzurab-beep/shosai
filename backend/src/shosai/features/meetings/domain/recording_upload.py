"""A desktop recording sent in parts (plan step 11, MT-D3): the draft's numbers and refusals.

The shipped clients cut the recording into parts of the size the server gives — 5 MiB, the
bucket's least part but the last — send the parts it does not have yet, in any order and
again when unsure, and complete. A part is at most 10 MiB and its number from 1 to 2 000.
The state the clients plan by is the bucket's own list of parts, never a memory of what
was sent. The refusals keep the draft's codes: 409 `private_meeting`, `no_upload`,
`no_parts`, `bad_part`, `empty_part`; 413 `part_too_large`.
"""

from dataclasses import dataclass, field
from typing import Final
from uuid import UUID

PART_SIZE: Final = 5 * 1024 * 1024
MAX_PART_BYTES: Final = 2 * PART_SIZE
MAX_PARTS: Final = 2000
FILENAME_MAX: Final = 200
# Насколько раньше встречи могла начаться запись: не дальше потолка встречи.
LEAD_MAX_MS: Final = 6 * 3600 * 1000

NO_UPLOAD: Final = "no_upload"
NO_PARTS: Final = "no_parts"
BAD_PART: Final = "bad_part"
EMPTY_PART: Final = "empty_part"
PART_TOO_LARGE: Final = "part_too_large"


@dataclass(frozen=True, slots=True)
class UploadState:
    """What the clients plan the rest of the upload by."""

    run_id: UUID
    upload_id: str
    part_size: int = PART_SIZE
    received: tuple[int, ...] = field(default=())
    bytes_received: int = 0
    completed: bool = False


def part_refusal(number: int, length: int) -> str | None:
    """Why a part of this number and length is refused, or None; its size is checked first."""
    if not 1 <= number <= MAX_PARTS:
        return BAD_PART
    if length == 0:
        return EMPTY_PART
    return None


def object_key(run_id: UUID) -> str:
    """Where a desktop recording is assembled, under `transient/` for at most 72 hours."""
    return f"transient/recording/run-{run_id}"

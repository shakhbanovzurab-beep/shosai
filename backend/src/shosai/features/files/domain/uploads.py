"""An upload's life and its parts (§10 Upload; FL-D1).

An upload is `pending` until its multipart upload completes and the object's size equals
the declared one (`ready`), else `rejected`; a ready upload is `claimed` once by the slice
it is for. One not completed or not claimed within 24 hours is `expired` — the bucket rule
aborts the same incomplete multipart upload. Parts are 16 MiB but the last: within the
store's 5 MiB minimum and 10 000 parts for any size up to the largest cap.
"""

import math
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final

PART_BYTES: Final = 16 * 1024**2
MIN_PART_BYTES: Final = 5 * 1024**2
MAX_PARTS: Final = 10_000
# Срок незавершённой или невостребованной загрузки; то же правило бакета (ADR 0055).
UPLOAD_TTL: Final = timedelta(hours=24)


class UploadState(StrEnum):
    """Where an upload stands."""

    PENDING = "pending"
    READY = "ready"
    CLAIMED = "claimed"
    REJECTED = "rejected"
    EXPIRED = "expired"


# Из какого состояния в какие можно перейти.
TRANSITIONS: Final = {
    UploadState.PENDING: frozenset({UploadState.READY, UploadState.REJECTED, UploadState.EXPIRED}),
    UploadState.READY: frozenset({UploadState.CLAIMED, UploadState.EXPIRED}),
    UploadState.CLAIMED: frozenset[UploadState](),
    UploadState.REJECTED: frozenset[UploadState](),
    UploadState.EXPIRED: frozenset[UploadState](),
}


def can_move(state: UploadState, to: UploadState) -> bool:
    """Whether an upload in `state` may become `to`."""
    return to in TRANSITIONS[state]


def holds_reservation(state: UploadState) -> bool:
    """Whether the upload's declared bytes are still reserved against the owner's quota."""
    return state in {UploadState.PENDING, UploadState.READY}


def part_sizes(size_bytes: int) -> list[int]:
    """The exact length of each part of an upload of `size_bytes`, in order."""
    if size_bytes < 1:
        message = "загрузка — хотя бы один байт"
        raise ValueError(message)
    count = math.ceil(size_bytes / PART_BYTES)
    if count > MAX_PARTS:
        message = f"загрузка больше {MAX_PARTS} частей"
        raise ValueError(message)
    return [PART_BYTES] * (count - 1) + [size_bytes - PART_BYTES * (count - 1)]


def deadline(created_at: datetime) -> datetime:
    """When an upload not claimed by then expires."""
    return created_at + UPLOAD_TTL


def completed_size_matches(declared: int, actual: int | None) -> bool:
    """Whether the completed object is exactly what was declared and signed."""
    return actual == declared

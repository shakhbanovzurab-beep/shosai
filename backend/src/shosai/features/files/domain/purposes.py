"""What an upload is for, its size cap and where its object lands (FL-D8, ADR 0055).

A File Manager upload is written to the file's final key in its owner's prefix; an upload
another slice claims lands under `transient/` and is moved by its claimer.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

MIB: Final = 1024**2
GIB: Final = 1024**3
# Файлов в одной загрузке File Manager (кабинет).
FILES_PER_REQUEST: Final = 20


class UploadPurpose(StrEnum):
    """Who takes the bytes once they are uploaded."""

    FILE_MANAGER = "file_manager"
    RECORDING = "recording"
    LEO_ATTACHMENT = "leo_attachment"
    TICKET_ATTACHMENT = "ticket_attachment"
    WORKSPACE_UPLOAD = "workspace_upload"
    APP_BUILD = "app_build"


@dataclass(frozen=True, slots=True)
class PurposeRules:
    """A purpose's cap and whether its object is a File Manager file from the start."""

    max_bytes: int
    in_file_manager: bool


PURPOSES: Final = {
    UploadPurpose.FILE_MANAGER: PurposeRules(2 * GIB, in_file_manager=True),
    UploadPurpose.RECORDING: PurposeRules(25 * MIB, in_file_manager=False),
    UploadPurpose.LEO_ATTACHMENT: PurposeRules(10 * MIB, in_file_manager=False),
    UploadPurpose.TICKET_ATTACHMENT: PurposeRules(10 * MIB, in_file_manager=False),
    UploadPurpose.WORKSPACE_UPLOAD: PurposeRules(25 * MIB, in_file_manager=False),
    UploadPurpose.APP_BUILD: PurposeRules(500 * MIB, in_file_manager=False),
}


def within_cap(purpose: UploadPurpose, size_bytes: int) -> bool:
    """Whether a declared size fits the purpose: at least one byte, at most its cap."""
    return 0 < size_bytes <= PURPOSES[purpose].max_bytes

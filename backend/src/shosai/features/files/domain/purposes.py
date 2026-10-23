"""What an upload is for, its size cap and where its object lands (FL-D8, ADR 0055, 0064).

A File Manager upload is written to the file's final key in its owner's prefix, and so is
an upload another slice holds through files (a task's attachment): both are counted in the
owner's storage from the reservation on. Any other upload another slice claims lands under
`transient/` and is moved by its claimer.
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
    TASK_ATTACHMENT = "task_attachment"


@dataclass(frozen=True, slots=True)
class PurposeRules:
    """A purpose's cap, whether its object is a File Manager file from the start, and whether
    files holds it for another slice (ADR 0064)."""

    max_bytes: int
    in_file_manager: bool
    held: bool = False

    @property
    def counted(self) -> bool:
        """Whether the bytes count in the owner's storage from the reservation on."""
        return self.in_file_manager or self.held


PURPOSES: Final = {
    UploadPurpose.FILE_MANAGER: PurposeRules(2 * GIB, in_file_manager=True),
    UploadPurpose.RECORDING: PurposeRules(25 * MIB, in_file_manager=False),
    UploadPurpose.LEO_ATTACHMENT: PurposeRules(10 * MIB, in_file_manager=False),
    UploadPurpose.TICKET_ATTACHMENT: PurposeRules(10 * MIB, in_file_manager=False),
    UploadPurpose.WORKSPACE_UPLOAD: PurposeRules(25 * MIB, in_file_manager=False),
    UploadPurpose.APP_BUILD: PurposeRules(500 * MIB, in_file_manager=False),
    UploadPurpose.TASK_ATTACHMENT: PurposeRules(25 * MIB, in_file_manager=False, held=True),
}


def within_cap(purpose: UploadPurpose, size_bytes: int) -> bool:
    """Whether a declared size fits the purpose: at least one byte, at most its cap."""
    return 0 < size_bytes <= PURPOSES[purpose].max_bytes

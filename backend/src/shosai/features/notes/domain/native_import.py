"""The native import's rules (plan step 9b): the draft's names, size and job stages.

The shipped clients send a recording by name and check it the same way before sending:
an extension from the draft's list, at most 25 MiB, not empty. The import's job is its
run seen through the five stages the 1.4.5 decoder knows — `uploading` until a stage
starts, `transcribing` through intake, transcription, diarization and alignment,
`enhancing` through the notes, then `ready`, or `failed` when the run fails. The stage
and the progress — the share of the run's stages finished — only ever grow.
"""

from collections.abc import Mapping
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Final

from shosai.features.notes.domain.runs import (
    STAGES,
    Progress,
    RunSource,
    RunState,
    Stage,
    StageRecord,
    StageStatus,
)

IMPORT_MAX_BYTES: Final = 25 * 1024 * 1024
FILENAME_MAX: Final = 512
# Расширения и типы черновика (services/import_jobs.py): их же проверяют клиенты 1.4.5.
MEDIA_TYPES: Final[Mapping[str, str]] = {
    ".mp3": "audio/mpeg", ".mpga": "audio/mpeg", ".mpeg": "audio/mpeg",
    ".m4a": "audio/mp4", ".mp4": "audio/mp4", ".aac": "audio/aac", ".wav": "audio/wav",
    ".ogg": "audio/ogg", ".oga": "audio/ogg", ".webm": "audio/webm", ".flac": "audio/flac",
}  # fmt: skip
TRANSCRIBING_STAGES: Final = frozenset({Stage.INTAKE, Stage.TRANSCRIBE, Stage.DIARIZE, Stage.ALIGN})
FINISHED: Final = frozenset({StageStatus.DONE, StageStatus.FAILED})


class JobStage(StrEnum):
    """An import job's stage, as the shipped clients decode it."""

    UPLOADING = "uploading"
    TRANSCRIBING = "transcribing"
    ENHANCING = "enhancing"
    READY = "ready"
    FAILED = "failed"


def extension_of(filename: str | None) -> str:
    """The file's extension in lower case, with its dot; empty without one."""
    return PurePosixPath(filename or "").suffix.lower()


def accepted_name(filename: str | None) -> bool:
    """Whether the file's extension is one the import takes."""
    return extension_of(filename) in MEDIA_TYPES


def media_type_of(filename: str) -> str:
    """The recording's media type by its extension, as the draft and the clients map it."""
    return MEDIA_TYPES[extension_of(filename)]


def stored_name(filename: str) -> str:
    """The file's name as it is kept: its last path segment, at most 512 characters."""
    return (PurePosixPath(filename.replace("\\", "/")).name or filename)[:FILENAME_MAX]


def job_progress(state: RunState, progress: Progress) -> tuple[JobStage, float]:
    """The job's stage and the share of the import run's stages finished."""
    stages = STAGES[RunSource.IMPORT]
    records = [progress.get(stage, StageRecord()) for stage in stages]
    share = round(sum(r.status in FINISHED for r in records) / len(stages), 2)
    if state in {RunState.SUCCEEDED, RunState.PARTIALLY_COMPLETED}:
        return JobStage.READY, 1.0
    if state is RunState.FAILED:
        return JobStage.FAILED, share
    started = [
        s for s, r in zip(stages, records, strict=True) if r.attempts or r.status in FINISHED
    ]
    if not started:
        return JobStage.UPLOADING, share
    current = next(
        (s for s, r in zip(stages, records, strict=True) if r.status not in FINISHED), stages[-1]
    )
    if current in TRANSCRIBING_STAGES:
        return JobStage.TRANSCRIBING, share
    return JobStage.ENHANCING, share

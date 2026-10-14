"""The rules of the export archive (identity plan §3.4, §3.6).

A person asks for an archive at most 3 times a day, with one open at a time. It is kept 7
days, downloaded by a link that lives 15 minutes, and a job whose run fails 3 times is
given up. Each owner's files go into a folder named after the owner.
"""

import re
from datetime import timedelta
from enum import StrEnum
from typing import Final
from uuid import UUID

EXPORT_PREFIX: Final = "exports/"
ARCHIVE_TYPE: Final = "application/zip"
EXPORT_KEPT: Final = timedelta(days=7)
REQUESTS_PER_DAY: Final = 3
MAX_ATTEMPTS: Final = 3
MANIFEST: Final = "manifest.json"
# Имя файла владельца: путь из латиницы, цифр, точек, дефисов и подчёркиваний, без «..».
FILE_NAME: Final = re.compile(r"(?!.*\.\.)[a-z0-9_][a-z0-9_./-]{0,200}")


class ExportState(StrEnum):
    """Where an export job is."""

    QUEUED = "queued"
    RUNNING = "running"
    READY = "ready"
    FAILED = "failed"


OPEN_STATES: Final = frozenset({ExportState.QUEUED, ExportState.RUNNING})


def archive_key(user_id: UUID, job_id: UUID) -> str:
    """Where a job's archive lives in the home's bucket."""
    return f"{EXPORT_PREFIX}{user_id}/{job_id}.zip"


def archive_path(owner: str, name: str) -> str:
    """The path of an owner's file in the archive; a name outside the rule is refused."""
    if not FILE_NAME.fullmatch(name):
        message = f"файл выгрузки {owner}: недопустимое имя {name!r}"
        raise ValueError(message)
    return f"{owner}/{name}"

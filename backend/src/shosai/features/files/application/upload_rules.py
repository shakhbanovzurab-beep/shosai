"""What an upload request must satisfy before anything is reserved or signed (FL-D8).

The size fits the purpose's cap; a File Manager file's name follows the cabinet's rules,
another purpose's name is 1 to 255 characters without control characters; a content type
that is not `type/subtype` becomes `application/octet-stream`. Each refusal has its code.
"""

import re
import unicodedata
from dataclasses import dataclass
from http import HTTPStatus
from typing import Final

from shosai.core.kernel.errors import AppError
from shosai.features.files.domain.names import NameRuleError, checked_name
from shosai.features.files.domain.purposes import PURPOSES, UploadPurpose, within_cap

FILENAME_MAX: Final = 255
CONTENT_TYPE: Final = re.compile(
    r"[a-z0-9][a-z0-9!#$&^_.+-]{0,126}/[a-z0-9][a-z0-9!#$&^_.+-]{0,126}"
)
DEFAULT_TYPE: Final = "application/octet-stream"


@dataclass(frozen=True, slots=True)
class UploadRequest:
    """What the client says it is about to upload."""

    purpose: UploadPurpose
    filename: str
    content_type: str
    size_bytes: int


def checked_request(request: UploadRequest) -> UploadRequest:
    """The request with its name and type normalised, or the refusal with its code."""
    if not within_cap(request.purpose, request.size_bytes):
        raise AppError(
            "upload_too_large",
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            params={"max_bytes": PURPOSES[request.purpose].max_bytes},
        )
    return UploadRequest(
        purpose=request.purpose,
        filename=checked_filename(request.purpose, request.filename),
        content_type=normalised_type(request.content_type),
        size_bytes=request.size_bytes,
    )


def checked_filename(purpose: UploadPurpose, raw: str) -> str:
    """A File Manager name by the cabinet's rules, any other by the generic one."""
    if PURPOSES[purpose].in_file_manager:
        try:
            return checked_name(raw)
        except NameRuleError as error:
            raise AppError(error.code, HTTPStatus.UNPROCESSABLE_CONTENT) from error
    name = raw.strip()
    broken = not 0 < len(name) <= FILENAME_MAX
    if broken or any(unicodedata.category(char) == "Cc" for char in name):
        raise AppError("filename_invalid", HTTPStatus.UNPROCESSABLE_CONTENT)
    return name


def normalised_type(raw: str) -> str:
    """The content type in lower case without parameters, or the generic binary type."""
    base = raw.split(";", 1)[0].strip().lower()
    return base if CONTENT_TYPE.fullmatch(base) else DEFAULT_TYPE

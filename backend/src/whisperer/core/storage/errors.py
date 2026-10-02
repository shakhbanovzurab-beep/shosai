"""Errors of the object storage that callers handle (target architecture §13.1, §14 rule 8).

The bucket in Russia is one point of failure for the files of both homes: when it does
not answer within the client's timeouts and retries, the request gets 503 and the rest of
the application keeps working. A missing object and a refused request are the caller's
to decide on; neither carries the key, which may contain a file name.
"""

from collections.abc import Sequence
from http import HTTPStatus
from typing import Final

from whisperer.core.kernel.errors import AppError

RETRY_AFTER_SECONDS: Final = 5


class StorageUnavailableError(AppError):
    """The bucket did not answer in time or failed on its side; the client retries later."""

    def __init__(self) -> None:
        super().__init__(
            "storage_unavailable",
            HTTPStatus.SERVICE_UNAVAILABLE,
            params={"retry_after_seconds": RETRY_AFTER_SECONDS},
        )


class ObjectNotFoundError(Exception):
    """The object or the multipart upload does not exist in the bucket."""


class StorageRejectedError(Exception):
    """The bucket refused the request: a wrong part list, a part too small, denied access.

    `code` is the S3 error code (`InvalidPart`, `EntityTooSmall`, `AccessDenied`…).
    """

    def __init__(self, code: str) -> None:
        super().__init__(f"хранилище отклонило запрос: {code}")
        self.code = code


class ObjectsNotDeletedError(Exception):
    """Some objects of a batch were not deleted; their keys are kept for a retry."""

    def __init__(self, keys: Sequence[str], codes: Sequence[str]) -> None:
        super().__init__(f"не удалено объектов: {len(keys)}; коды: {', '.join(sorted(set(codes)))}")
        self.keys = tuple(keys)

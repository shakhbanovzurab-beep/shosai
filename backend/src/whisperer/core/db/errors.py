"""Errors of database access that the caller and the client are told about."""

from http import HTTPStatus
from typing import Final

from sqlalchemy import exc

from whisperer.core.kernel.errors import AppError
from whisperer.core.kernel.homes import Home

RETRY_AFTER_SECONDS: Final = 5


class HomeUnavailableError(AppError):
    """The scope's home cannot take a transaction now; the client retries later (§13.2).

    Other homes keep working: an outage of the Russian database stops only its users.
    """

    def __init__(self, home: Home) -> None:
        super().__init__(
            "home_unavailable",
            HTTPStatus.SERVICE_UNAVAILABLE,
            params={"retry_after_seconds": RETRY_AFTER_SECONDS},
        )
        self.home = home


def connection_failure(error: exc.SQLAlchemyError) -> str:
    """The driver's first line about a failed connection, for the log.

    psycopg gives no SQLSTATE for a refused connection, so a wrong password and a lost
    link are told apart only by this text: the server address and the server's reason,
    never the password or a statement's values.
    """
    cause = error.orig if isinstance(error, exc.DBAPIError) else error
    lines = str(cause).splitlines()
    return lines[0] if lines else type(cause).__qualname__

"""The id of a request: kept from the client when safe, otherwise generated (ADR 0008).

The id reaches every log line of the request, the `X-Request-ID` response header and the
`error.request_id` of an error body, so support finds the request from what a user sees.
"""

import re
from collections.abc import MutableMapping
from typing import Any

from shosai.core.kernel.ids import new_id

REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_HEADER_KEY = REQUEST_ID_HEADER.lower().encode("ascii")
# Чужое значение попадает в каждую строку лога: перевод строки подделал бы соседние
# записи, мегабайтная строка раздула бы их. Не прошло проверку — генерируем своё.
_SAFE_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")
_SCOPE_KEY = "shosai.request_id"

type Scope = MutableMapping[str, Any]


class RequestIdMissingError(Exception):
    """The scope has no request id: the request did not pass the request boundary."""


def assign_request_id(scope: Scope) -> str:
    """Keep the client's `X-Request-ID` if it is safe, else a new UUIDv7; store it in the scope."""
    request_id = _incoming_request_id(scope) or new_id().hex
    scope[_SCOPE_KEY] = request_id
    return request_id


def request_id_of(scope: Scope) -> str:
    """The id the request boundary assigned to this request."""
    request_id = scope.get(_SCOPE_KEY)
    if not isinstance(request_id, str):
        message = "у запроса нет request_id: граница запроса не установлена в приложении"
        raise RequestIdMissingError(message)
    return request_id


def _incoming_request_id(scope: Scope) -> str | None:
    for name, value in scope.get("headers", ()):
        if name == _REQUEST_ID_HEADER_KEY:
            candidate = value.decode("latin-1")
            return candidate if _SAFE_REQUEST_ID.fullmatch(candidate) else None
    return None

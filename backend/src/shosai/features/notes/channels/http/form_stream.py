"""A `multipart/form-data` body read as it arrives, for one file field (plan step 9b).

The body is fed to python-multipart's parser chunk by chunk: the file field's name and
type come from its part's headers, its bytes as they arrive, so no more than a chunk is
held and nothing is written to disk. `drain` reads what is left of the body, discarding
it, so a refusal answered mid-way still reaches a client that keeps sending; past the
hard limit the body is no longer read (413 `file_too_large`). A body that is not
multipart, or has no such field, is 422 `validation_error`; a malformed one is 400
`bad_request`.
"""

from collections import deque
from collections.abc import AsyncIterator
from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING, Final

from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import MultipartParser, parse_options_header
from starlette.requests import Request

from shosai.core.kernel.errors import AppError

if TYPE_CHECKING:
    from python_multipart.multipart import MultipartCallbacks

FORM_DATA: Final = b"multipart/form-data"


@dataclass(frozen=True, slots=True)
class FilePart:
    """The file field's name and type as its part's headers give them."""

    filename: str | None
    content_type: str | None


@dataclass(frozen=True, slots=True)
class _PartEnd:
    """The file field's part ended."""


class FormStream:
    """One file field of a request's multipart body, read as the client sends it."""

    def __init__(self, request: Request, field: str, *, limit: int) -> None:
        kind, options = parse_options_header(request.headers.get("content-type"))
        boundary = options.get(b"boundary") if kind == FORM_DATA else None
        self._body = request.stream()
        self._field, self._limit, self._read = field.encode(), limit, 0
        self._events: deque[FilePart | bytes | _PartEnd] = deque()
        self._ended = False
        self._header = (bytearray(), bytearray())
        self._headers: dict[bytes, bytes] = {}
        self._target, self._found = False, False
        self._parser = MultipartParser(boundary, self._callbacks()) if boundary else None

    async def file(self) -> FilePart:
        """The file field's headers; `validation_error` when the body has none."""
        while (event := await self._next()) is not None:
            if isinstance(event, FilePart):
                return event
        raise AppError("validation_error", HTTPStatus.UNPROCESSABLE_ENTITY)

    async def chunks(self) -> AsyncIterator[bytes]:
        """The file field's bytes until its part ends."""
        while (event := await self._next()) is not None and not isinstance(event, _PartEnd):
            if isinstance(event, bytes):
                yield event

    async def drain(self) -> None:
        """Read the rest of the body, up to the limit, and drop it."""
        while not self._ended:
            await self._pump(strict=False)
        self._events.clear()

    async def _next(self) -> FilePart | bytes | _PartEnd | None:
        while not self._events:
            if self._ended:
                return None
            await self._pump(strict=True)
        return self._events.popleft()

    async def _pump(self, *, strict: bool) -> None:
        if self._parser is None:
            self._ended = True
            return
        chunk = await anext(self._body, None)
        if chunk is None:
            self._ended = True
            return
        self._read += len(chunk)
        if self._read > self._limit:
            self._ended = True
            if strict:
                raise AppError("file_too_large", HTTPStatus.CONTENT_TOO_LARGE)
            return
        try:
            self._parser.write(chunk)
        except MultipartParseError:
            self._ended = True
            raise AppError("bad_request", HTTPStatus.BAD_REQUEST) from None

    def _callbacks(self) -> MultipartCallbacks:
        name, value = self._header

        def header_field(data: bytes, start: int, end: int) -> None:
            name.extend(data[start:end])

        def header_value(data: bytes, start: int, end: int) -> None:
            value.extend(data[start:end])

        def header_end() -> None:
            self._headers[bytes(name).lower()] = bytes(value)
            name.clear()
            value.clear()

        def part_data(data: bytes, start: int, end: int) -> None:
            if self._target and end > start:
                self._events.append(data[start:end])

        def part_end() -> None:
            if self._target:
                self._events.append(_PartEnd())
            self._target = False

        return {
            "on_header_field": header_field,
            "on_header_value": header_value,
            "on_header_end": header_end,
            "on_headers_finished": self._headers_finished,
            "on_part_data": part_data,
            "on_part_end": part_end,
        }

    def _headers_finished(self) -> None:
        _, disposition = parse_options_header(self._headers.get(b"content-disposition"))
        kind = self._headers.get(b"content-type")
        self._headers = {}
        if self._found or disposition.get(b"name") != self._field:
            return
        self._target = self._found = True
        filename = disposition.get(b"filename")
        self._events.append(
            FilePart(
                filename.decode("utf-8", "replace") if filename is not None else None,
                kind.decode("latin-1") if kind is not None else None,
            )
        )

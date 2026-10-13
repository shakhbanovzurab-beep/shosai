"""An opaque cursor over a collection's sort key (§10; F1 audit A10).

A cursor is the position of the last item a page returned: the values of the collection's
sort key, a unique column last. It is base64url of a small JSON with the collection's name
and a format version, so a cursor of one collection is refused by another, and a cursor of
an older format by a newer one. It is not secret and not signed: a client that edits one
only moves inside data its scope already lets it read, so a cursor that does not decode,
belongs elsewhere or does not fit the position's model is `invalid_cursor` (422), never a
500.
"""

import base64
import binascii
import json
import re
from http import HTTPStatus
from typing import Final

from pydantic import BaseModel, ValidationError

from shosai.core.kernel.errors import AppError

CURSOR_FORMAT: Final = 1
CURSOR_MAX_LENGTH: Final = 512
COLLECTION_NAME: Final = re.compile(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+")


class InvalidCursorError(AppError):
    """The cursor did not come from this collection's previous page."""

    def __init__(self) -> None:
        super().__init__("invalid_cursor", HTTPStatus.UNPROCESSABLE_ENTITY)


class CursorCodec[P: BaseModel]:
    """Encodes and decodes the cursors of one collection, whose position model is `P`."""

    def __init__(self, collection: str, position: type[P]) -> None:
        if not COLLECTION_NAME.fullmatch(collection):
            message = "коллекция курсора — «срез.коллекция» в snake_case"
            raise ValueError(message)
        self._collection = collection
        self._position = position

    def encode(self, position: P) -> str:
        """The cursor of a position; padding is dropped, the token is URL-safe."""
        document = {
            "c": self._collection,
            "v": CURSOR_FORMAT,
            "p": position.model_dump(mode="json"),
        }
        raw = json.dumps(document, separators=(",", ":")).encode()
        token = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
        if len(token) > CURSOR_MAX_LENGTH:
            message = f"курсор коллекции {self._collection} длиннее {CURSOR_MAX_LENGTH} символов"
            raise ValueError(message)
        return token

    def decode(self, token: str) -> P:
        """The position a cursor of this collection names; `InvalidCursorError` otherwise."""
        try:
            raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
            document = json.loads(raw)
        except binascii.Error, ValueError:
            raise InvalidCursorError from None
        if (
            not isinstance(document, dict)
            or document.get("c") != self._collection
            or document.get("v") != CURSOR_FORMAT
        ):
            raise InvalidCursorError
        try:
            return self._position.model_validate(document.get("p"))
        except ValidationError:
            raise InvalidCursorError from None

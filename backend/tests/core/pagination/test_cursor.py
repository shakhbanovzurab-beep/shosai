"""A cursor names a position of one collection; anything else is `invalid_cursor` (§10)."""

import base64
import json
import uuid
from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import BaseModel

from shosai.core.pagination.cursor import CursorCodec, InvalidCursorError


class SessionPosition(BaseModel):
    """Where a page of meetings ended: the start time and the id, unique last."""

    started_at: datetime
    id: uuid.UUID


NOTES = CursorCodec("probe.meetings", SessionPosition)
POSITION = SessionPosition(started_at=datetime(2026, 10, 13, 9, 30, tzinfo=UTC), id=uuid.uuid7())


def token_of(document: object) -> str:
    """A cursor built by hand, as a client could forge it."""
    raw = json.dumps(document).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def test_a_cursor_returns_the_position_it_was_made_from() -> None:
    token = NOTES.encode(POSITION)

    assert NOTES.decode(token) == POSITION
    assert "=" not in token
    assert token.isascii()


@pytest.mark.parametrize(
    "token",
    [
        CursorCodec("probe.notes", SessionPosition).encode(POSITION),
        token_of({"c": "probe.meetings", "v": 2, "p": POSITION.model_dump(mode="json")}),
        token_of({"c": "probe.meetings", "v": 1, "p": {"id": "not-a-uuid"}}),
        token_of(["probe.meetings", 1]),
        "%%%",
        "",
    ],
)
def test_a_cursor_of_another_collection_format_or_shape_is_refused(token: str) -> None:
    with pytest.raises(InvalidCursorError) as raised:
        NOTES.decode(token)

    assert (raised.value.code, raised.value.status) == ("invalid_cursor", 422)


@given(st.text(max_size=600))
def test_any_text_either_decodes_or_is_refused_as_invalid(token: str) -> None:
    try:
        NOTES.decode(token)
    except InvalidCursorError:
        return


def test_a_collection_is_named_by_its_slice() -> None:
    with pytest.raises(ValueError, match="коллекция"):
        CursorCodec("meetings", SessionPosition)

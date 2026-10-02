"""An event is declared with its type and version and carries no free text (§12, §16.8)."""

import re
from datetime import UTC, date, datetime
from decimal import Decimal
from ipaddress import IPv4Address
from typing import Annotated, Any, ClassVar, Literal
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import BaseModel, StringConstraints, ValidationError

from tests.core.events.bench import NoteState, NoteWritten
from whisperer.core.events.domain_event import DomainEvent, EventCode, EventDeclarationError

CODE_ALPHABET = re.compile(r"[a-z0-9_.:-]{1,64}")


class Nested(BaseModel):
    """A model inside an event: its fields would escape the rule."""

    note: str


type Ids = tuple[UUID, ...]
type FreeText = Annotated[str, StringConstraints(max_length=10)]


class EveryKind(DomainEvent):
    """An event with a field of every allowed kind."""

    event_type: ClassVar[str] = "probe.kinds.listed"
    version: ClassVar[int] = 3

    record_id: UUID
    count: int
    share: float
    amount: Decimal
    flag: bool
    at: datetime
    day: date
    state: NoteState
    code: EventCode
    maybe: UUID | None = None
    ids: Ids = ()
    codes: frozenset[EventCode] = frozenset()


def declare(annotation: object) -> type[DomainEvent]:
    """A probe event class with one field of the given type."""
    namespace: dict[str, Any] = {
        "__annotations__": {
            "event_type": ClassVar[str],
            "version": ClassVar[int],
            "value": annotation,
        },
        "event_type": "probe.field.checked",
        "version": 1,
    }
    return type("Probe", (DomainEvent,), namespace)


def test_an_event_of_every_allowed_kind_round_trips_through_json() -> None:
    event = EveryKind(
        record_id=uuid4(),
        count=3,
        share=0.5,
        amount=Decimal("12.50"),
        flag=True,
        at=datetime(2026, 10, 2, 12, 0, tzinfo=UTC),
        day=date(2026, 10, 2),
        state=NoteState.FINAL,
        code="payment:declined",
        ids=(uuid4(), uuid4()),
        codes=frozenset({"a", "b"}),
    )

    assert EveryKind.model_validate(event.model_dump(mode="json")) == event


@pytest.mark.parametrize(
    "annotation",
    [
        str,
        str | None,
        tuple[str, ...],
        FreeText,
        Annotated[str, StringConstraints(pattern=r"^[a-z]+$")],
        dict[str, int],
        list[UUID],
        tuple[UUID, str],
        Nested,
        Any,
        IPv4Address,
        bytes,
        Literal["draft"],
    ],
)
def test_a_field_that_can_hold_free_text_or_a_structure_is_refused(annotation: object) -> None:
    with pytest.raises(EventDeclarationError, match="поле value"):
        declare(annotation)


@pytest.mark.parametrize(
    ("event_type", "version"),
    [
        ("probe.written", 1),
        ("Probe.note.written", 1),
        ("probe.note.written.twice", 1),
        ("probe.note." + "x" * 60, 1),
        ("probe.note.written", 0),
        ("probe.note.written", True),
    ],
)
def test_a_type_or_version_out_of_form_is_refused(event_type: str, version: object) -> None:
    namespace: dict[str, Any] = {
        "__annotations__": {"event_type": ClassVar[str], "version": ClassVar[int]},
        "event_type": event_type,
        "version": version,
    }

    with pytest.raises(EventDeclarationError):
        type("Probe", (DomainEvent,), namespace)


def test_a_subclass_declares_its_own_type_and_version() -> None:
    with pytest.raises(EventDeclarationError, match="event_type"):
        type("Rewritten", (NoteWritten,), {})


def test_an_event_is_frozen_and_ignores_fields_it_does_not_know() -> None:
    record_id = uuid4()
    event = NoteWritten.model_validate(
        {"record_id": str(record_id), "state": "draft", "added_later": 5}
    )

    assert event == NoteWritten(record_id=record_id, state=NoteState.DRAFT)
    with pytest.raises(ValidationError):
        event.record_id = uuid4()  # type: ignore[misc]


@given(st.text(max_size=80))
def test_a_code_holds_only_its_closed_alphabet(text: str) -> None:
    try:
        event = NoteWritten(record_id=UUID(int=1), state=NoteState.DRAFT, reason=text)
    except ValidationError:
        assert not CODE_ALPHABET.fullmatch(text)
        return
    assert event.reason is not None
    assert CODE_ALPHABET.fullmatch(event.reason)


@pytest.mark.parametrize("text", ["anna@example.com", "Anna Petrova", "Ежедневная планёрка"])
def test_an_email_a_name_or_a_title_is_not_a_code(text: str) -> None:
    with pytest.raises(ValidationError):
        NoteWritten(record_id=UUID(int=1), state=NoteState.DRAFT, reason=text)

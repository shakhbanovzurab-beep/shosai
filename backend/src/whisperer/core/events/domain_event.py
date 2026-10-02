"""Domain events: facts one slice publishes for others (target architecture §12).

A slice declares each event once, in its `contracts` module, as a frozen Pydantic model
with a stable `event_type` (`slice.object.happened`, past tense: a fact, not a command)
and the `version` of its fields. A new field is optional, so a consumer reads what an
older producer wrote; a change a consumer cannot read gets a new event type.

Events carry no personal data (§12, §16.8): every field is an id, a number, a flag, a
time, an enum or an `EventCode` — a short code from a closed alphabet — or a tuple or
frozenset of them. The rule is checked when the class is defined, so an email, a name
or a title cannot enter an event: the import of such a class fails (draft lesson: the
draft's events carried addresses and meeting titles).
"""

import re
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from types import NoneType, UnionType
from typing import Annotated, ClassVar, Final, TypeAliasType, Union, get_args, get_origin
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

EVENT_TYPE: Final = re.compile(r"[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*")
EVENT_TYPE_MAX_LENGTH: Final = 64

# Код — значение из закрытого набора (статус, причина, вид), а не текст человека.
type EventCode = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_.:-]{1,64}$")]

ALLOWED_VALUE_TYPES: Final[tuple[type, ...]] = (UUID, bool, int, float, Decimal, datetime, date)


class EventDeclarationError(TypeError):
    """An event class breaks the rules of event declarations; the message names the rule."""


class DomainEvent(BaseModel):
    """A fact a slice publishes; subclasses set `event_type` and `version`."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    event_type: ClassVar[str]
    version: ClassVar[int]

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: object) -> None:
        """Check the declaration as soon as the class is built."""
        super().__pydantic_init_subclass__(**kwargs)
        check_event_class(cls)


def check_event_class(event: type[DomainEvent]) -> None:
    """Refuse an event class without its own type and version, or with a field of another kind."""
    own = vars(event)
    event_type = own.get("event_type")
    if (
        not isinstance(event_type, str)
        or len(event_type) > EVENT_TYPE_MAX_LENGTH
        or not EVENT_TYPE.fullmatch(event_type)
    ):
        message = (
            f"событие {event.__name__}: event_type — «срез.объект.что_случилось» в snake_case, "
            f"не длиннее {EVENT_TYPE_MAX_LENGTH} символов, объявленный в самом классе"
        )
        raise EventDeclarationError(message)
    version = own.get("version")
    if type(version) is not int or version < 1:
        message = f"событие {event_type}: version — целое число от 1, объявленное в самом классе"
        raise EventDeclarationError(message)
    for name, field in event.model_fields.items():
        if not is_event_value(field.annotation):
            message = (
                f"событие {event_type}: поле {name} — не идентификатор, число, флаг, время, "
                "перечисление или EventCode; персональные данные и свободный текст в событие "
                "не попадают"
            )
            raise EventDeclarationError(message)


def is_event_value(annotation: object) -> bool:
    """Whether a field of this type may be part of an event."""
    if annotation is EventCode:
        return True
    if isinstance(annotation, TypeAliasType):
        return is_event_value(annotation.__value__)
    origin = get_origin(annotation)
    if origin is None:
        return isinstance(annotation, type) and (
            issubclass(annotation, Enum) or annotation in ALLOWED_VALUE_TYPES
        )
    return is_event_container(origin, get_args(annotation))


def is_event_container(origin: object, arguments: tuple[object, ...]) -> bool:
    """Whether an optional value, a tuple or a frozenset holds only event values."""
    if origin is Annotated:
        return is_event_value(arguments[0])
    if origin is Union or origin is UnionType:
        return all(argument is NoneType or is_event_value(argument) for argument in arguments)
    if origin is tuple:
        return len(arguments) == 2 and arguments[1] is Ellipsis and is_event_value(arguments[0])
    if origin is frozenset:
        return is_event_value(arguments[0])
    return False

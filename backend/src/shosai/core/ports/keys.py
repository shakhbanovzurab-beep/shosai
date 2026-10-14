"""Port keys and bindings (identity plan §3.2, ADR 0045 point 11).

A slice that offers a service to other slices declares a `PortKey` for it in its
`contracts.py`, next to the protocol the service implements. The slice that implements it
binds an instance in its `FeatureParts.provides`; a slice that needs it names the key in
`FeatureModule.requires` and resolves it from `CoreServices.ports` when a request or task
runs, after every slice of the process is built. Keys are values rather than classes, so
a protocol type is never passed where a concrete class is expected.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

PORT_NAME: Final = re.compile(r"[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*")


class Cardinality(StrEnum):
    """How many slices may bind a port."""

    # Ровно одна реализация: аутентификатор, чтение согласий.
    ONE = "one"
    # Сколько угодно, в порядке срезов: вклады в /v1/auth/me, реестры.
    MANY = "many"


@dataclass(frozen=True, slots=True)
class PortKey[P]:
    """The name and cardinality of a port whose implementations are of type `P`."""

    # «срез.порт»: имя называет владельца контракта.
    name: str
    cardinality: Cardinality = Cardinality.ONE

    def __post_init__(self) -> None:
        if not PORT_NAME.fullmatch(self.name):
            message = f"порт {self.name!r}: имя — «срез.порт» в snake_case"
            raise ValueError(message)

    def bind(self, implementation: P) -> PortBinding[P]:
        """A binding of this port to an implementation, for `FeatureParts.provides`."""
        return PortBinding(self, implementation)


@dataclass(frozen=True, slots=True)
class PortBinding[P]:
    """One implementation of a port, contributed by the slice that built it."""

    key: PortKey[P]
    implementation: P

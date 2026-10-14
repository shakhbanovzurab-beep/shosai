"""Every port binding of the process, filled once all slices are built.

Composition installs the bindings of every slice and checks them against what the slices
require before the process serves anything: a required port nobody binds, or a
single-implementation port bound twice, stops the start. Reading before installation is a
composition error, never a silent empty answer.
"""

from collections.abc import Iterable, Mapping, Sequence
from types import MappingProxyType
from typing import Any, cast

from shosai.core.ports.keys import Cardinality, PortBinding, PortKey


class PortDirectory:
    """The bound implementations by port name."""

    def __init__(self) -> None:
        self._bound: Mapping[str, tuple[object, ...]] | None = None

    def install(
        self, bindings: Iterable[PortBinding[Any]], required: Sequence[PortKey[Any]] = ()
    ) -> None:
        """Register the bindings once and check the required ports and cardinalities."""
        if self._bound is not None:
            message = "порты уже установлены"
            raise RuntimeError(message)
        found: dict[str, list[object]] = {}
        keys: dict[str, PortKey[Any]] = {}
        for binding in bindings:
            known = keys.setdefault(binding.key.name, binding.key)
            if known != binding.key:
                message = f"порт {binding.key.name} объявлен с разной кратностью"
                raise ValueError(message)
            found.setdefault(binding.key.name, []).append(binding.implementation)
        doubled = sorted(
            name
            for name, implementations in found.items()
            if keys[name].cardinality is Cardinality.ONE and len(implementations) > 1
        )
        missing = sorted(
            {
                key.name
                for key in required
                if key.cardinality is Cardinality.ONE and key.name not in found
            }
        )
        if doubled or missing:
            message = f"порты привязаны дважды {doubled}, требуются без привязки {missing}"
            raise ValueError(message)
        self._bound = MappingProxyType({name: tuple(items) for name, items in found.items()})

    def get[P](self, key: PortKey[P]) -> P:
        """The one implementation of a single-implementation port."""
        if key.cardinality is not Cardinality.ONE:
            message = f"порт {key.name} допускает много реализаций: читайте его через all()"
            raise TypeError(message)
        implementations = self._installed().get(key.name, ())
        if not implementations:
            message = f"порт {key.name} не привязан ни одним срезом"
            raise LookupError(message)
        return cast("P", implementations[0])

    def all[P](self, key: PortKey[P]) -> tuple[P, ...]:
        """Every implementation of a port, in the order of the slices; empty if none."""
        return cast("tuple[P, ...]", self._installed().get(key.name, ()))

    def _installed(self) -> Mapping[str, tuple[object, ...]]:
        if self._bound is None:
            message = "порты читаются до установки: композиция не закончена"
            raise RuntimeError(message)
        return self._bound

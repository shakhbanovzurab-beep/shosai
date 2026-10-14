"""The port directory: bindings checked once, read only after installation (ADR 0045)."""

import pytest

from shosai.core.ports.directory import PortDirectory
from shosai.core.ports.keys import Cardinality, PortKey

GREETER = PortKey[str]("greetings.greeter")
LISTENERS = PortKey[str]("greetings.listener", Cardinality.MANY)


def test_a_single_port_returns_its_one_implementation() -> None:
    directory = PortDirectory()
    directory.install([GREETER.bind("hello")], required=[GREETER])

    assert directory.get(GREETER) == "hello"


def test_a_many_port_returns_every_binding_in_order_and_nothing_when_unbound() -> None:
    directory = PortDirectory()
    directory.install([LISTENERS.bind("first"), LISTENERS.bind("second")])
    empty = PortDirectory()
    empty.install([])

    assert directory.all(LISTENERS) == ("first", "second")
    assert empty.all(LISTENERS) == ()


def test_a_required_port_without_binding_is_refused_by_name() -> None:
    with pytest.raises(ValueError, match=r"greetings\.greeter"):
        PortDirectory().install([], required=[GREETER])


def test_a_single_port_bound_twice_is_refused() -> None:
    with pytest.raises(ValueError, match=r"greetings\.greeter"):
        PortDirectory().install([GREETER.bind("a"), GREETER.bind("b")])


def test_one_name_with_two_cardinalities_is_refused() -> None:
    twin = PortKey[str]("greetings.greeter", Cardinality.MANY)

    with pytest.raises(ValueError, match="кратностью"):
        PortDirectory().install([GREETER.bind("a"), twin.bind("b")])


def test_reading_before_installation_is_a_composition_error() -> None:
    with pytest.raises(RuntimeError):
        PortDirectory().get(GREETER)


def test_installing_twice_is_refused() -> None:
    directory = PortDirectory()
    directory.install([])

    with pytest.raises(RuntimeError):
        directory.install([])


def test_an_unbound_single_port_and_a_many_port_read_as_single_are_errors() -> None:
    directory = PortDirectory()
    directory.install([])

    with pytest.raises(LookupError):
        directory.get(GREETER)
    with pytest.raises(TypeError):
        directory.get(LISTENERS)


@pytest.mark.parametrize("name", ["greeter", "Greetings.greeter", "greetings.greeter.extra"])
def test_a_port_name_is_slice_dot_port(name: str) -> None:
    with pytest.raises(ValueError, match=r"срез\.порт"):
        PortKey[str](name)

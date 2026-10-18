"""Files' public surface follows core's rules (files plan §3.2)."""

import inspect

from shosai.composition.features import FEATURES
from shosai.core.events.domain_event import DomainEvent
from shosai.core.ports.keys import PortKey
from shosai.features.files import contracts
from shosai.features.files.contracts import events
from shosai.features.files.module import FILES


def test_every_published_event_is_registered_and_named_for_the_slice() -> None:
    declared = {
        value
        for value in vars(events).values()
        if inspect.isclass(value) and issubclass(value, DomainEvent) and value is not DomainEvent
    }

    assert set(FILES.events) == declared
    assert all(event.event_type.startswith("files.") for event in FILES.events)
    assert FILES in FEATURES


def test_the_ports_are_named_for_the_slice() -> None:
    keys = {value.name for value in vars(contracts).values() if isinstance(value, PortKey)}

    assert keys == {"files.uploads", "files.file_reader", "files.index_status"}

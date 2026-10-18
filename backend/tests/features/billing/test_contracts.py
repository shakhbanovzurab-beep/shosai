"""Billing's public surface follows core's rules (billing plan §3.2)."""

import inspect

from shosai.composition.features import FEATURES
from shosai.core.events.domain_event import DomainEvent
from shosai.core.ports.keys import PortKey
from shosai.features.billing import contracts
from shosai.features.billing.contracts import events
from shosai.features.billing.module import BILLING


def test_every_published_event_is_registered_and_named_for_the_slice() -> None:
    declared = {
        value
        for value in vars(events).values()
        if inspect.isclass(value) and issubclass(value, DomainEvent) and value is not DomainEvent
    }

    assert set(BILLING.events) == declared
    assert all(event.event_type.startswith("billing.") for event in BILLING.events)
    assert BILLING in FEATURES


def test_the_ports_are_named_for_the_slice() -> None:
    keys = {value.name for value in vars(contracts).values() if isinstance(value, PortKey)}

    assert keys == {
        "billing.entitlements", "billing.minutes_allowance", "billing.usage_tombstones",
        "billing.meeting_minutes", "billing.token_allowance",
    }  # fmt: skip

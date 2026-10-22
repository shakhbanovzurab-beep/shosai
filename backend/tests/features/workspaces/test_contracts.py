"""Workspaces' public surface: its events and ports follow core's rules (workspaces plan §3.2)."""

import inspect
from importlib import import_module

from shosai.composition.features import FEATURES
from shosai.core.events.domain_event import DomainEvent
from shosai.core.ports.keys import Cardinality, PortKey
from shosai.features.workspaces import contracts
from shosai.features.workspaces.contracts import events
from shosai.features.workspaces.domain.audit import AuditAction
from shosai.features.workspaces.module import WORKSPACES


def declared_events() -> set[type[DomainEvent]]:
    return {
        value
        for value in vars(events).values()
        if inspect.isclass(value) and issubclass(value, DomainEvent) and value is not DomainEvent
    }


def test_every_published_event_is_registered_with_the_slice() -> None:
    assert set(WORKSPACES.events) == declared_events()
    assert len(WORKSPACES.events) == len(set(WORKSPACES.events))


def test_events_are_named_for_the_slice_and_unique() -> None:
    types = [event.event_type for event in WORKSPACES.events]

    assert all(name.startswith("workspaces.") for name in types)
    assert len(types) == len(set(types))


def test_the_slice_is_composed_with_the_others() -> None:
    assert WORKSPACES in FEATURES


def test_ports_are_single_and_named_for_the_slice() -> None:
    keys = [value for value in vars(contracts).values() if isinstance(value, PortKey)]

    assert {key.name for key in keys} == {
        "workspaces.access_policy",
        "workspaces.membership_reader",
        "workspaces.workspace_reader",
        "workspaces.audit_log",
        "workspaces.seat_allowance",
        "workspaces.knowledge_transfer",
    }
    assert all(key.cardinality is Cardinality.ONE for key in keys)


def test_the_seat_port_is_not_required_until_billing_binds_it() -> None:
    # Без billing старт не должен стоять: вступления отклоняются, а не процесс (ADR 0053 п. 7).
    assert contracts.SEAT_ALLOWANCE not in WORKSPACES.requires


def test_the_audit_log_accepts_exactly_the_domains_actions() -> None:
    revision = import_module("shosai.migrations.versions.2026_10_17_c41d7e9a2b85_workspaces")

    assert ", ".join(f"'{action.value}'" for action in AuditAction) == revision.AUDIT_ACTIONS

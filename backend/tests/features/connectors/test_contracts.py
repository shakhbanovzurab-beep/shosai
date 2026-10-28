"""Connectors' public surface follows core's rules (connectors plan §3.3)."""

import inspect
import uuid

import pytest

from shosai.composition.features import FEATURES
from shosai.core.events.domain_event import DomainEvent
from shosai.core.ports.keys import Cardinality, PortKey
from shosai.features.connectors import contracts
from shosai.features.connectors.contracts import (
    ConnectorUses,
    FlowCookie,
    NeedsReconnectError,
    ProviderBusyError,
    ProviderRefusedError,
    ProviderResponse,
    events,
)
from shosai.features.connectors.contracts.events import ConnectionBroken, RevokeReason
from shosai.features.connectors.domain.catalogue import App
from shosai.features.connectors.domain.states import Problem
from shosai.features.connectors.module import CONNECTORS


def test_the_published_events_are_registered_and_named_for_the_slice() -> None:
    declared = {
        value
        for value in vars(events).values()
        if inspect.isclass(value) and issubclass(value, DomainEvent) and value is not DomainEvent
    }

    assert set(CONNECTORS.events) == declared
    assert {event.event_type for event in CONNECTORS.events} == {
        "connectors.connection.connected",
        "connectors.connection.broken",
        "connectors.connection.revoked",
    }
    assert CONNECTORS in FEATURES


def test_the_ports_are_named_for_the_slice_and_uses_take_many_bindings() -> None:
    keys = [value for value in vars(contracts).values() if isinstance(value, PortKey)]

    assert {key.name for key in keys} == {
        "connectors.connections",
        "connectors.provider_access",
        "connectors.installations",
        "connectors.uses",
    }
    assert contracts.CONNECTOR_USES.cardinality is Cardinality.MANY
    assert ConnectorUses("tasks", frozenset({App.JIRA})).apps == {App.JIRA}


def test_an_event_names_the_connection_by_ids_and_codes_only() -> None:
    event = ConnectionBroken(
        connection_id=uuid.uuid4(), user_id=uuid.uuid4(), app=App.GMAIL,
        problem=Problem.REFRESH_REFUSED,
    )  # fmt: skip

    assert event.org_id is None
    assert set(type(event).model_fields) == {"connection_id", "user_id", "org_id", "app", "problem"}
    assert {reason.value for reason in RevokeReason} >= {"disconnected", "erased", "replaced"}


def test_errors_carry_codes_a_client_can_word() -> None:
    reconnect = NeedsReconnectError(Problem.SCOPE_MISSING)
    busy = ProviderBusyError(10_000)

    assert (reconnect.code, reconnect.status, dict(reconnect.params)) == (
        "needs_reconnect", 409, {"problem": "scope_missing"},
    )  # fmt: skip
    assert busy.retry_after_seconds == 3600
    assert ProviderBusyError(0).params["retry_after"] == 1


def test_a_refusal_keeps_a_provider_code_only_when_it_is_a_code() -> None:
    assert dict(ProviderRefusedError(400, "invalid_request").params) == {
        "provider_status": 400, "provider_code": "invalid_request",
    }  # fmt: skip
    assert dict(ProviderRefusedError(403, "an error with spaces").params) == {
        "provider_status": 403,
    }  # fmt: skip


def test_a_response_body_that_is_not_json_is_a_refusal() -> None:
    assert ProviderResponse(200, {}, b'{"ok": true}').json() == {"ok": True}
    with pytest.raises(ProviderRefusedError):
        ProviderResponse(200, {}, b"<html>").json()


def test_the_flow_cookie_is_http_only_secure_and_lax() -> None:
    arguments = FlowCookie("shosai_connect", "binder", "/v1/connectors/oauth", 600)

    assert arguments.set_cookie_arguments() == {
        "key": "shosai_connect", "value": "binder", "path": "/v1/connectors/oauth",
        "max_age": 600, "httponly": True, "secure": True, "samesite": "lax",
    }  # fmt: skip

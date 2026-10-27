"""Agent's public surface follows core's rules (agent plan §3.2)."""

import inspect
import uuid

import pytest

from shosai.composition.features import FEATURES
from shosai.core.events.domain_event import DomainEvent
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.keys import PortKey
from shosai.features.agent import contracts
from shosai.features.agent.contracts import ProposalRefusedError, ProposalRequest, events
from shosai.features.agent.contracts.events import TurnCompleted
from shosai.features.agent.domain.actions import ProposalOrigin
from shosai.features.agent.module import AGENT


def test_the_published_event_is_registered_and_named_for_the_slice() -> None:
    declared = {
        value
        for value in vars(events).values()
        if inspect.isclass(value) and issubclass(value, DomainEvent) and value is not DomainEvent
    }

    assert set(AGENT.events) == declared
    assert {event.event_type for event in AGENT.events} == {"agent.turn.completed"}
    assert AGENT in FEATURES


def test_the_ports_are_named_for_the_slice() -> None:
    keys = {value.name for value in vars(contracts).values() if isinstance(value, PortKey)}

    assert keys == {
        "agent.action_proposals",
        "agent.turn_router",
        "agent.friction_judge",
        "agent.injection_judge",
        "agent.memory_recall",
        "agent.profile_facts",
        "agent.skill_reader",
    }


def test_the_event_names_the_turn_by_ids_only() -> None:
    event = TurnCompleted(thread_id=uuid.uuid4(), run_id=uuid.uuid4(), user_id=uuid.uuid4())

    assert set(event.model_dump(mode="json")) >= {"thread_id", "run_id", "user_id"}


def request(scope: TenancyScope, origin_key: str) -> ProposalRequest:
    return ProposalRequest(
        scope=scope,
        thread_id=uuid.uuid4(),
        message_id=uuid.uuid4(),
        tool="tasks.create",
        arguments={"tasks": []},
        origin=ProposalOrigin.PROPOSAL_PORT,
        origin_key=origin_key,
        language="en",
    )


def test_a_proposal_is_made_as_a_person_with_a_bounded_origin_key() -> None:
    person = TenancyScope(Home.EU, user_id=uuid.uuid4())

    assert request(person, "digest:1").origin_key == "digest:1"
    with pytest.raises(ValueError, match="от имени человека"):
        request(TenancyScope(Home.EU), "digest:1")
    with pytest.raises(ValueError, match="120"):
        request(person, "k" * 121)


def test_a_refused_proposal_is_a_422_naming_the_tool_s_reason() -> None:
    error = ProposalRefusedError("forbidden")

    assert (error.code, int(error.status), dict(error.params)) == (
        "proposal_refused",
        422,
        {"reason": "forbidden"},
    )

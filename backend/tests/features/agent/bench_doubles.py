"""What the turn bench lets a test module change: the probe's tools, the stream's silence, the
judges of a card's friction, the router of a turn's toolsets, the judge of injected text, the
judge of a turn's effort and memory's recall and profile core."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Final, Protocol

import pytest

from shosai.core.ports.keys import PortBinding
from shosai.features.agent.contracts import FrictionJudge, InjectionJudge, TurnRouter
from shosai.features.agent.contracts.effort import EffortJudge
from shosai.features.agent.contracts.memory import (
    MEMORY_RECALL,
    PROFILE_FACTS,
    MemoryRecall,
    ProfileFacts,
)
from tests.features.agent.tool_doubles import ProbeTools

# Тесты на тишину журнала ждут секунду, а не 45 с production.
SILENCE: Final = timedelta(seconds=1)


class MemoryPorts(MemoryRecall, ProfileFacts, Protocol):
    """Memory as a turn sees it: recall and the profile core, from one double."""


def memory_bindings(memories: Sequence[MemoryPorts]) -> list[PortBinding[Any]]:
    """Each double bound as both of memory's ports."""
    return [
        binding
        for memory in memories
        for binding in (MEMORY_RECALL.bind(memory), PROFILE_FACTS.bind(memory))
    ]


@dataclass(frozen=True, slots=True)
class BenchDoubles:
    """The probe's tools, how long a run's log may stay silent before its record is read, and
    the judges and the router bound beside the rules."""

    tools: ProbeTools
    silence: timedelta
    judges: tuple[FrictionJudge, ...] = ()
    routers: tuple[TurnRouter, ...] = ()
    injections: tuple[InjectionJudge, ...] = ()
    memories: tuple[MemoryPorts, ...] = ()
    efforts: tuple[EffortJudge, ...] = ()


@pytest.fixture
def probe_tools() -> ProbeTools:
    """The probe's tools; a module that needs others overrides this fixture."""
    return ProbeTools()


@pytest.fixture
def stream_silence() -> timedelta:
    """The stream's silence; a module that measures production's reads overrides it."""
    return SILENCE


@pytest.fixture
def friction_judges() -> tuple[FrictionJudge, ...]:
    """No judge: the rule alone decides; a module that judges cards overrides it."""
    return ()


@pytest.fixture
def turn_routers() -> tuple[TurnRouter, ...]:
    """No router: the rule alone routes; a module that ranks toolsets overrides it."""
    return ()


@pytest.fixture
def injection_judges() -> tuple[InjectionJudge, ...]:
    """No judge of injected text; a module that judges pieces overrides it."""
    return ()


@pytest.fixture
def effort_judges() -> tuple[EffortJudge, ...]:
    """No judge of a turn's effort: turns keep the tier's; a module that judges overrides it."""
    return ()


@pytest.fixture
def memory_doubles() -> tuple[MemoryPorts, ...]:
    """No memory: turns are built without it; a module that recalls facts overrides it."""
    return ()


@dataclass(frozen=True, slots=True)
class LeoDoubles:
    """The judges, the router and memory bound beside the rules."""

    judges: tuple[FrictionJudge, ...]
    routers: tuple[TurnRouter, ...]
    injections: tuple[InjectionJudge, ...]
    memories: tuple[MemoryPorts, ...]
    efforts: tuple[EffortJudge, ...] = ()


@pytest.fixture
def leo_doubles(
    friction_judges: tuple[FrictionJudge, ...],
    turn_routers: tuple[TurnRouter, ...],
    injection_judges: tuple[InjectionJudge, ...],
    memory_doubles: tuple[MemoryPorts, ...],
    effort_judges: tuple[EffortJudge, ...],
) -> LeoDoubles:
    """What a module binds beside the rules."""
    return LeoDoubles(
        friction_judges, turn_routers, injection_judges, memory_doubles, effort_judges
    )


@pytest.fixture
def bench_doubles(
    probe_tools: ProbeTools, stream_silence: timedelta, leo_doubles: LeoDoubles
) -> BenchDoubles:
    """All of them together, for the bench."""
    return BenchDoubles(
        probe_tools, stream_silence, leo_doubles.judges, leo_doubles.routers,
        leo_doubles.injections, leo_doubles.memories, leo_doubles.efforts,
    )  # fmt: skip

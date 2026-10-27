"""What the turn bench lets a test module change: the probe's tools, the stream's silence, the
judges of a card's friction, the router of a turn's toolsets and the judge of injected text."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Final

import pytest

from shosai.features.agent.contracts import FrictionJudge, InjectionJudge, TurnRouter
from tests.features.agent.tool_doubles import ProbeTools

# Тесты на тишину журнала ждут секунду, а не 45 с production.
SILENCE: Final = timedelta(seconds=1)


@dataclass(frozen=True, slots=True)
class BenchDoubles:
    """The probe's tools, how long a run's log may stay silent before its record is read, and
    the judges and the router bound beside the rules."""

    tools: ProbeTools
    silence: timedelta
    judges: tuple[FrictionJudge, ...] = ()
    routers: tuple[TurnRouter, ...] = ()
    injections: tuple[InjectionJudge, ...] = ()


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
def bench_doubles(
    probe_tools: ProbeTools,
    stream_silence: timedelta,
    friction_judges: tuple[FrictionJudge, ...],
    turn_routers: tuple[TurnRouter, ...],
    injection_judges: tuple[InjectionJudge, ...],
) -> BenchDoubles:
    """All of them together, for the bench."""
    return BenchDoubles(
        probe_tools, stream_silence, friction_judges, turn_routers, injection_judges
    )

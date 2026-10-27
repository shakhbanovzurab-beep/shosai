"""What the turn bench lets a test module change: the probe's tools and the stream's silence."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Final

import pytest

from tests.features.agent.tool_doubles import ProbeTools

# Тесты на тишину журнала ждут секунду, а не 45 с production.
SILENCE: Final = timedelta(seconds=1)


@dataclass(frozen=True, slots=True)
class BenchDoubles:
    """The probe's tools and how long a run's log may stay silent before its record is read."""

    tools: ProbeTools
    silence: timedelta


@pytest.fixture
def probe_tools() -> ProbeTools:
    """The probe's tools; a module that needs others overrides this fixture."""
    return ProbeTools()


@pytest.fixture
def stream_silence() -> timedelta:
    """The stream's silence; a module that measures production's reads overrides it."""
    return SILENCE


@pytest.fixture
def bench_doubles(probe_tools: ProbeTools, stream_silence: timedelta) -> BenchDoubles:
    """The two together, for the bench."""
    return BenchDoubles(probe_tools, stream_silence)

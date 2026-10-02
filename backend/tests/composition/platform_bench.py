"""The platform of a process built in this test process over the run's slot."""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass

from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry

from tests.harness.process_environ import slot_environ
from tests.harness.run_slot import RunSlot
from tests.harness.settings import HarnessSettings
from whisperer.composition.platform import Platform, open_platform
from whisperer.composition.telemetry import ProcessTelemetry
from whisperer.core.config.loading import Settings, load_settings
from whisperer.core.config.roles import ProcessRole
from whisperer.core.features import FeatureModule


@dataclass(frozen=True, slots=True)
class PlatformBench:
    """A platform, the settings it was built from and where it reports."""

    platform: Platform
    settings: Settings
    telemetry: ProcessTelemetry

    def sample(self, name: str, **labels: str) -> float:
        """A metric sample of the platform's registry, 0 when never recorded."""
        return self.telemetry.registry.get_sample_value(name, labels) or 0.0


@asynccontextmanager
async def platform_over_slot(
    run_slot: RunSlot,
    harness_settings: HarnessSettings,
    features: Sequence[FeatureModule],
    role: ProcessRole = ProcessRole.API,
) -> AsyncIterator[PlatformBench]:
    """The platform a process of the role builds with the slices, closed after the block."""
    settings = load_settings(slot_environ(run_slot, harness_settings))
    telemetry = ProcessTelemetry(CollectorRegistry(), TracerProvider(shutdown_on_exit=False))
    async with open_platform(settings, role, telemetry, features) as platform:
        yield PlatformBench(platform, settings, telemetry)

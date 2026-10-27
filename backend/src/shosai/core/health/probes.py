"""Dependency probes and their aggregation for the readiness probe (F1 plan §3.11, F1-C2).

Every dependency is checked at the same time, each within 2 s, and reported as `ok` or
`down`. A dependency that is down does not fail readiness: all processes share the same
dependencies, and failing readiness on one would pull every process from the edge — EU
users would lose service over a Russian outage (§13.2). Outages are alerted through
metrics instead. A probe declares the errors that mean "down"; any other error is a bug
in the probe and is raised, not hidden as an outage.
"""

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Final, Literal

import structlog

PROBE_TIMEOUT: Final = timedelta(seconds=2)
log = structlog.stdlib.get_logger(__name__)

type ProbeStatus = Literal["ok", "down"]


@dataclass(frozen=True, slots=True)
class DependencyProbe:
    """A named check of one dependency and the errors that mean it is down."""

    name: str
    check: Callable[[], Awaitable[object]]
    failures: tuple[type[Exception], ...]


async def probe_dependencies(
    probes: Sequence[DependencyProbe], within: timedelta = PROBE_TIMEOUT
) -> Mapping[str, ProbeStatus]:
    """The status of every dependency, checked concurrently, each within `within`."""
    names = [probe.name for probe in probes]
    if len(set(names)) != len(names):
        message = "имена проб зависимостей повторяются"
        raise ValueError(message)
    statuses = await asyncio.gather(*(run_probe(probe, within) for probe in probes))
    return dict(zip(names, statuses, strict=True))


async def run_probe(probe: DependencyProbe, within: timedelta) -> ProbeStatus:
    """`ok` when the check returns in time, `down` when it fails as the probe declares."""
    failures: tuple[type[Exception], ...] = (*probe.failures, TimeoutError)
    try:
        async with asyncio.timeout(within.total_seconds()):
            await probe.check()
    except failures as error:
        log.warning(
            "Зависимость не ответила пробе готовности",
            dependency=probe.name,
            error_type=type(error).__qualname__,
        )
        return "down"
    return "ok"


def check_probe_names(probes: Sequence[DependencyProbe]) -> None:
    """Refuse two probes with one name: the readiness report could not tell them apart."""
    names = [probe.name for probe in probes]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        message = f"пробы готовности названы дважды: {', '.join(duplicates)}"
        raise ValueError(message)

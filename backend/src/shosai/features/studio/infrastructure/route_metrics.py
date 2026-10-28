"""The metrics of resolving models and prompts for people (studio plan §3.7).

Every series starts at zero for every role and reason, so the ticket rules' `increase` sees
the first substitution and the first role left without a default. The label is `studio_role`:
`role` is the process's own (api, ws, workers) on every series.
"""

from typing import Final

from prometheus_client import CollectorRegistry, Counter, Histogram

from shosai.features.studio.domain.roles import ModelRole
from shosai.features.studio.domain.routing import Substitution

SUBSTITUTIONS: Final = "shosai_studio_route_substitutions_total"
RESOLUTIONS: Final = "shosai_studio_resolution_seconds"
UNCONFIGURED: Final = "shosai_studio_role_unconfigured_total"
SKILLS_LEFT_OUT: Final = "shosai_studio_skills_left_out_total"
# Разрешение — снимок в памяти и одна-две строки человека: миллисекунды, хвост — сеть до базы.
BUCKETS: Final = (0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)


class RouteMetrics:
    """Resolutions, the substitutions among them, roles without a default, skills left out."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._substitutions = Counter(
            SUBSTITUTIONS,
            "Resolutions where the person's choice did not answer, by role and reason",
            ["studio_role", "reason"],
            registry=registry,
        )
        self._resolutions = Histogram(
            RESOLUTIONS,
            "Time to resolve a role's model for a person",
            ["studio_role"],
            buckets=BUCKETS,
            registry=registry,
        )
        self._unconfigured = Counter(
            UNCONFIGURED,
            "Resolutions refused because the role has no default that can answer",
            ["studio_role"],
            registry=registry,
        )
        self._skills_left_out = Counter(
            SKILLS_LEFT_OUT, "Skills left out of a role's prompt over its budget", registry=registry
        )
        for role in ModelRole:
            self._resolutions.labels(studio_role=role.value)
            self._unconfigured.labels(studio_role=role.value)
            for reason in Substitution:
                self._substitutions.labels(studio_role=role.value, reason=reason.value)

    def resolved(self, role: ModelRole, seconds: float) -> None:
        """Time one resolution."""
        self._resolutions.labels(studio_role=role.value).observe(seconds)

    def substituted(self, role: ModelRole, reason: Substitution) -> None:
        """Count a resolution the person's choice did not answer."""
        self._substitutions.labels(studio_role=role.value, reason=reason.value).inc()

    def unconfigured(self, role: ModelRole) -> None:
        """Count a resolution refused for want of a default."""
        self._unconfigured.labels(studio_role=role.value).inc()

    def skills_left_out(self, count: int) -> None:
        """Count the skills a prompt left out over its budget."""
        if count:
            self._skills_left_out.inc(count)

"""The skills store's calls out in numbers (agent step 15): closed label sets, no repository.

`shosai_agent_skill_source_calls_total{source, outcome}` counts each call to GitHub or to
skills.sh by how it ended — `ok`, `not_found`, `rate_limited`, `too_large`, `unavailable` — so
an exhausted GitHub limit or a directory that changed its answer shows before people say so.
"""

from enum import StrEnum

from prometheus_client import CollectorRegistry, Counter


class SourceCall(StrEnum):
    """Where the store reads skills from."""

    GITHUB = "github"
    SKILLS_SH = "skills_sh"


class SkillMetrics:
    """The store's counters, in the process's registry."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._calls = Counter(
            "shosai_agent_skill_source_calls",
            "Обращения хранилища навыков к GitHub и skills.sh по исходу",
            ("source", "outcome"),
            registry=registry,
        )

    def called(self, source: SourceCall, outcome: str) -> None:
        """A call out ended."""
        self._calls.labels(source.value, outcome).inc()

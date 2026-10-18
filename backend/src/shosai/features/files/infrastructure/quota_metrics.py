"""Files' quota metrics: what FL-D2 and FL-D10 did and the two gauges of inv-11 (§16.4).

`shosai_files_quota_actions_total{action}` counts marks, clears, reminders and removals;
`shosai_files_leo_quota_actions_total{action}` the same steps over the knowledge limit.
`shosai_files_quota_drift{home}` holds the owners whose counter differs from the sum of
their files at the last reconciliation, `shosai_files_orphaned_objects{home}` the objects
no row names; both stay at zero while the invariant holds.
"""

from typing import Final

from prometheus_client import CollectorRegistry, Counter, Gauge

from shosai.core.kernel.homes import Home
from shosai.features.files.domain.quota import QuotaAction

QUOTA_DRIFT: Final = "shosai_files_quota_drift"
ORPHANED_OBJECTS: Final = "shosai_files_orphaned_objects"


class QuotaMetrics:
    """The quota's counter and the reconciliation's gauges, in the process's registry."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._actions = Counter(
            "shosai_files_quota_actions",
            "Шаги квоты по FL-D2: отметка, снятие отметки, напоминание, удаление файлов",
            ("action",),
            registry=registry,
        )
        self._leo_actions = Counter(
            "shosai_files_leo_quota_actions",
            "Шаги лимита знаний по FL-D10: отметка, снятие, напоминание, выключение файлов из Leo",
            ("action",),
            registry=registry,
        )
        self._drift = Gauge(
            QUOTA_DRIFT,
            "Владельцы, у которых счётчик места расходится с суммой их файлов",
            ("home",),
            registry=registry,
        )
        self._orphans = Gauge(
            ORPHANED_OBJECTS,
            "Объекты бакета старше суток, на которые не указывает ни одна строка",
            ("home",),
            registry=registry,
        )

    def acted(self, action: QuotaAction) -> None:
        """One quota step was taken."""
        self._actions.labels(action=action.value).inc()

    def leo_acted(self, action: QuotaAction) -> None:
        """One step over the knowledge limit was taken."""
        self._leo_actions.labels(action=action.value).inc()

    def drift(self, home: Home, owners: int) -> None:
        """The reconciliation's count of owners whose counter drifted."""
        self._drift.labels(home=home.value).set(owners)

    def orphans(self, home: Home, objects: int) -> None:
        """The reconciliation's count of objects no row names."""
        self._orphans.labels(home=home.value).set(objects)

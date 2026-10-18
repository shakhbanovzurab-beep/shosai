"""Files' invariant monitors (§16.4): inv-11's counters and orphans, from the reconciliation.

The daily reconciliation sets both gauges per home; anything above zero pages.
"""

from shosai.core.observability.objectives import InvariantMonitor, StaysAtMost
from shosai.features.files.infrastructure.quota_metrics import ORPHANED_OBJECTS, QUOTA_DRIFT

FILES_MONITORS = (
    InvariantMonitor(
        name="storage_counter_drift",
        invariant="inv-11",
        summary="Счётчик занятого места расходится с файлами",
        explanation=(
            "Ежедневная сверка нашла людей, у которых учтённое место не равно сумме их файлов. "
            "Квота считает неверно: человеку могут отказать в загрузке зря или пустить сверх "
            "тарифа. Id людей — в журнале сверки; счётчик правят только после разбора причины."
        ),
        condition=StaysAtMost(QUOTA_DRIFT),
    ),
    InvariantMonitor(
        name="orphaned_object",
        invariant="inv-11",
        summary="В бакете есть файлы, на которые не указывает ни одна строка",
        explanation=(
            "Сверка нашла в бакете дома объекты старше суток без строки файла и без ожидающего "
            "удаления. Это байты, которые никто не видит и за которые платит сервис; они могли "
            "остаться после сбоя удаления. Нужно найти причину, прежде чем удалять объекты."
        ),
        condition=StaysAtMost(ORPHANED_OBJECTS),
    ),
)

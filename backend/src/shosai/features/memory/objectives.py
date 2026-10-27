"""What memory pages for and what its dashboard shows (memory plan §3.8, target architecture §16.4).

One invariant pages: a fact a writer created after the person switched memory off — zero is the
only healthy value. Recall's time and the admission's lag are shown on memory's dashboard with no
promise; the admission's lag and the extraction's failures raise tickets (`tickets.yml`).
"""

from typing import Final

from shosai.core.observability.objectives import (
    InvariantMonitor,
    Journey,
    StaysAtMost,
    TrackedLatency,
)
from shosai.features.memory.infrastructure.metrics import (
    ADMISSION_LAG,
    RECALL_SECONDS,
    WRITTEN_WHILE_OFF,
)

LEO_MEMORY: Final = Journey("leo_memory", "Память Leo")

MEMORY_MONITORS: Final = (
    InvariantMonitor(
        name="memory_written_while_off",
        invariant="§16.4: выключенная память ничего не пишет",
        summary="Память Leo записала факт после того, как человек её выключил",
        explanation=(
            "Почасовая проверка нашла факт, который Leo сохранил уже после того, как человек "
            "выключил память в настройках. Leo нарушил выбор человека: он запоминает то, что "
            "запоминать запретили. Число людей — в журнале проверки; найдите, какой путь записи "
            "не прочитал переключатель в своей транзакции."
        ),
        condition=StaysAtMost(WRITTEN_WHILE_OFF),
    ),
)

MEMORY_TRACKED: Final = (
    TrackedLatency(
        LEO_MEMORY,
        "Вспоминание в ходе: 95 % быстрее этой линии",
        "Сколько память ищет факты к вопросу человека, вместе с вектором вопроса. Срок — 350 "
        "миллисекунд: опоздавшее вспоминание ход не ждёт, ответ идёт без него.",
        RECALL_SECONDS,
        (("все ходы", ""),),
    ),
    TrackedLatency(
        LEO_MEMORY,
        "Разбор хода памятью: 95 % быстрее этой линии",
        "Сколько проходит от конца ответа Leo до того, как память записала, что из хода "
        "запомнить. Строка «Leo может запомнить» под ответом появляется после этого; больше "
        "минуты подряд — тикет.",
        ADMISSION_LAG,
        (("все ходы", ""),),
    ),
)

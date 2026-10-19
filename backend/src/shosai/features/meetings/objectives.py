"""Meetings' invariant monitors (§16.4): inv-6 from the settle sweep, inv-7 from its backlog.

A line capture showed that a settled meeting does not hold pages at once; ended meetings no
sweep settled within a quarter of an hour page too, since a spoken one may have no run.
"""

from shosai.core.observability.objectives import InvariantMonitor, NeverIncreases, StaysAtMost
from shosai.features.meetings.infrastructure.transcript_metrics import LINES_MISSING, UNSETTLED

MEETINGS_MONITORS = (
    InvariantMonitor(
        name="transcript_line_lost",
        invariant="inv-6",
        summary="Показанная строка расшифровки не сохранена",
        explanation=(
            "Обход закончившейся встречи нашёл, что capture показал человеку строки, которых в "
            "базе нет. Человек видел текст, а заметки и поиск его не получат. Строки могли "
            "потеряться в очереди Valkey или при сбое слива; id встречи — в журнале обхода."
        ),
        condition=NeverIncreases(LINES_MISSING),
    ),
    InvariantMonitor(
        name="meeting_left_unprocessed",
        invariant="inv-7",
        summary="Закончившиеся встречи не досчитаны дольше четверти часа",
        explanation=(
            "Есть встречи, закончившиеся больше 15 минут назад, которые обход ещё не проверил. "
            "Среди них может быть встреча с речью без прогона: заметки к ней не появятся. "
            "Обход падает или не успевает; смотрите задачу meetings.settle_ended."
        ),
        condition=StaysAtMost(UNSETTLED),
    ),
)

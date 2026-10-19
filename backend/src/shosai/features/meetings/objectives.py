"""Meetings' objectives (§16.3) and invariant monitors (§16.4).

The post-meeting journey: notes within 10 minutes of the meeting's end for 95 % of runs,
and fewer than 1 % of runs failed. A line capture showed that a settled meeting does not
hold pages at once; ended meetings no sweep settled within a quarter of an hour page too,
since a spoken one may have no run.
"""

from shosai.core.observability.objectives import (
    EventRatio,
    InvariantMonitor,
    Journey,
    LatencyRatio,
    NeverIncreases,
    ServiceLevelObjective,
    StaysAtMost,
)
from shosai.features.meetings.infrastructure.pipeline_metrics import NOTES_READY, RUNS
from shosai.features.meetings.infrastructure.transcript_metrics import LINES_MISSING, UNSETTLED

POST_MEETING = Journey("post_meeting", "Заметки после встречи")
# Граница корзины гистограммы: 10 минут (§16.3, nfr-8).
NOTES_THRESHOLD = "600"

MEETINGS_OBJECTIVES = (
    ServiceLevelObjective(
        name="post_meeting_failures",
        journey=POST_MEETING,
        summary="Заметки после встреч не появляются: обработка встреч заканчивается ошибкой",
        promise="после встречи её обработка заканчивается без ошибки в 99 % случаев",
        target=0.99,
        indicator=EventRatio(total=RUNS, bad=f'{RUNS}{{outcome="failed"}}'),
    ),
    ServiceLevelObjective(
        name="post_meeting_latency",
        journey=POST_MEETING,
        summary="Заметки после встреч появляются с опозданием",
        promise="заметки готовы в течение 10 минут после конца встречи в 95 % случаев",
        target=0.95,
        indicator=LatencyRatio(NOTES_READY, 'source=~".+"', NOTES_THRESHOLD),
    ),
)

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

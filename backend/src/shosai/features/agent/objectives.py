"""The agent slice's objectives and invariant monitors (§16.3, §16.4; agent plan §3.6).

A Leo turn ends without a failure of the platform — `failed`, `process_lost`, `turn_deadline`;
the model's own unavailability is the provider's — in 99 % of turns, and the platform's own
time on a turn of a person in the EU home stays under half a second in 95 % of turns (step 5b).
An approved action is carried out, or refused with a code, within 30 s in 99 % of approvals;
an outcome nobody can tell counts against it (step 9a2). No item of an action is ever executed
twice or without the person's approval (L-N5): the hourly check's two gauges stay at 0. The
turn's dashboard also tracks, with no promise or alert, the platform's time for people of both
homes — Russian ones' are measured and reported, not paged (L-N1) — and the worker's pickup
of a turn (step 17).
"""

from shosai.core.observability.objectives import (
    EventRatio,
    InvariantMonitor,
    Journey,
    LatencyRatio,
    ServiceLevelObjective,
    StaysAtMost,
    TrackedLatency,
)
from shosai.features.agent.infrastructure.action_metrics import (
    APPROVED_ACTIONS,
    EXECUTED_TWICE,
    EXECUTED_UNAPPROVED,
)
from shosai.features.agent.infrastructure.run_metrics import (
    OVERHEAD,
    PICKUP,
    PLATFORM_FAILURES,
    TURNS,
)

LEO_TURN = Journey("leo_turn", "Ход Leo")
LEO_ACTION = Journey("leo_action", "Действие Leo после одобрения")
# Граница корзины гистограммы: 0,5 с — цель накладных расходов платформы (§16.3).
OVERHEAD_THRESHOLD = "0.5"

AGENT_OBJECTIVES = (
    ServiceLevelObjective(
        name="leo_turn_failures",
        journey=LEO_TURN,
        summary="Ходы Leo заканчиваются сбоем платформы",
        promise="ход Leo заканчивается без сбоя платформы в 99 % случаев",
        target=0.99,
        indicator=EventRatio(
            total=TURNS, bad=f'{TURNS}{{outcome=~"{"|".join(PLATFORM_FAILURES)}"}}'
        ),
    ),
    ServiceLevelObjective(
        name="leo_turn_overhead",
        journey=LEO_TURN,
        summary="Платформа задерживает ходы Leo",
        promise="платформа тратит на ход Leo человека из ЕС не больше 0,5 с в 95 % ходов",
        target=0.95,
        indicator=LatencyRatio(OVERHEAD, 'home="eu"', OVERHEAD_THRESHOLD),
    ),
    ServiceLevelObjective(
        name="leo_approved_actions",
        journey=LEO_ACTION,
        summary="Одобренные действия Leo выполняются медленно или с неизвестным исходом",
        promise="одобренное действие Leo выполняется или отклоняется с понятной причиной за "
        "30 секунд в 99 % случаев",
        target=0.99,
        indicator=EventRatio(
            total=APPROVED_ACTIONS, bad=f'{APPROVED_ACTIONS}{{result!="in_time"}}'
        ),
    ),
)

AGENT_MONITORS = (
    InvariantMonitor(
        name="leo_item_executed_twice",
        invariant="L-N5",
        summary="Действие Leo выполнено дважды",
        explanation=(
            "Почасовая проверка аудита нашла пункт одобренного действия Leo, который срез "
            "применил больше одного раза: например, две одинаковые задачи вместо одной. Ключ "
            "пункта должен был это исключить. Ид действий — в журнале проверки; посмотрите, "
            "какой срез исполнил пункт повторно."
        ),
        condition=StaysAtMost(EXECUTED_TWICE),
    ),
    InvariantMonitor(
        name="leo_item_executed_unapproved",
        invariant="L-N5",
        summary="Действие Leo выполнено без одобрения",
        explanation=(
            "Почасовая проверка аудита нашла пункт действия Leo, исполненный без одобрения "
            "человека: Leo мог изменить данные человека без его решения. Ид действий — в "
            "журнале проверки; срочно найдите путь, который исполнил пункт в обход шлюза "
            "действий."
        ),
        condition=StaysAtMost(EXECUTED_UNAPPROVED),
    ),
)

AGENT_TRACKED = (
    TrackedLatency(
        LEO_TURN,
        "Время платформы на ходе Leo: 95 % ходов быстрее этой линии",
        "Сколько своего времени платформа тратит на ход — без модели и инструментов — у людей, "
        "чьи данные хранятся в ЕС и в России. Для ЕС обещаны 0,5 секунды (график выше). База "
        "России дальше от сервера в ЕС, каждая транзакция там дольше: это время измеряется и "
        "показывается здесь, но срочных сообщений не шлёт.",
        OVERHEAD,
        (("ЕС", 'home="eu"'), ("Россия", 'home="ru"')),
    ),
    TrackedLatency(
        LEO_TURN,
        "Воркер берёт ход: 95 % ходов быстрее этой линии",
        "Сколько проходит от приёма вопроса — с его записью в базу — до того, как воркер ходов "
        "начал ход. Это время входит во время платформы; рост значит, что воркерам ходов не "
        "хватает места или Valkey отвечает медленно.",
        PICKUP,
        (("все ходы", ""),),
    ),
)

"""The agent slice's objectives (§16.3; agent plan §3.6, step 5b).

A Leo turn ends without a failure of the platform — `failed`, `process_lost`, `turn_deadline`;
the model's own unavailability is the provider's — in 99 % of turns, and the platform's own
time on a turn of a person in the EU home stays under half a second in 95 % of turns.
"""

from shosai.core.observability.objectives import (
    EventRatio,
    Journey,
    LatencyRatio,
    ServiceLevelObjective,
)
from shosai.features.agent.infrastructure.run_metrics import OVERHEAD, PLATFORM_FAILURES, TURNS

LEO_TURN = Journey("leo_turn", "Ход Leo")
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
)

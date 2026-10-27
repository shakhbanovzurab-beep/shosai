"""The Decision Layer's invariant monitor and tickets (§16.3, §16.4; decisions plan §3.8).

No outcome is ever less careful than its consumer's rule (ADR 0069): an answer that would be
is overruled and counted, and the count pages; the one exception, a person's consent read by
voice.approval, leaves only as an active version's answer in time — any changed outcome that
leaves another way is the rule's, and pages too. Three tickets watch Jev without waking anyone:
decisions refused because Jev's endpoint is off OpenRouter's zero-retention list or its status
went three days unread (DL-D1); Jev answering within the policy's deadline for 95 % of the
decisions asked of it; and the rule's fallback at most one decision in five of those a policy
in force was consulted for. The journey's dashboard also tracks the time a caller waited for a
decision, by point.
"""

from typing import Final

from shosai.core.observability.objectives import (
    AlertClass,
    EventRatio,
    InvariantMonitor,
    Journey,
    NeverIncreases,
    ServiceLevelObjective,
    TrackedLatency,
)
from shosai.features.decisions.infrastructure.metrics import (
    DECISION_SECONDS,
    OUTSIDE_BOUNDS,
    REQUESTS,
    UNSAFE_OUTCOMES,
)

LEO_DECISIONS = Journey("leo_decisions", "Решения Leo")
# Решения, по которым спрашивали политику в силе: ни правило без политики, ни «решать нечего».
CONSULTED: Final = f'{REQUESTS}{{reason!~"nothing_to_decide|policy_off"}}'
# Решения, за которыми ходили к Jev: ответ в срок, опоздание, сбой провайдера, негодный ответ.
ASKED: Final = f'{REQUESTS}{{reason=~"judged|deadline|provider_error|contract"}}'

DECISIONS_OBJECTIVES = (
    ServiceLevelObjective(
        name="leo_decisions_zero_retention",
        journey=LEO_DECISIONS,
        summary="Решения Leo идут по правилам: Jev не подтверждён как хранящий ноль",
        promise="решения Leo не остаются без Jev из-за того, что его адрес у OpenRouter "
        "перестал быть адресом с нулевым хранением данных, в 99 % случаев",
        target=0.99,
        indicator=EventRatio(total=CONSULTED, bad=f'{REQUESTS}{{reason="not_zdr"}}'),
        alerting=AlertClass.TICKET,
    ),
    ServiceLevelObjective(
        name="leo_decisions_jev_on_time",
        journey=LEO_DECISIONS,
        summary="Jev отвечает на решения Leo позже срока",
        promise="Jev отвечает на решение Leo в его срок в 95 % случаев",
        target=0.95,
        indicator=EventRatio(total=ASKED, bad=f'{REQUESTS}{{reason="deadline"}}'),
        alerting=AlertClass.TICKET,
    ),
    ServiceLevelObjective(
        name="leo_decisions_fallbacks",
        journey=LEO_DECISIONS,
        summary="Решения Leo слишком часто уходят в запасное правило",
        promise="решение Leo, для которого есть политика, принимается ею, а не запасным "
        "правилом, в 80 % случаев",
        target=0.8,
        indicator=EventRatio(total=CONSULTED, bad=f'{REQUESTS}{{source="fallback"}}'),
        alerting=AlertClass.TICKET,
    ),
)

DECISIONS_MONITORS = (
    InvariantMonitor(
        name="decision_unsafe_outcome",
        invariant="ADR 0069",
        summary="Политика решений Leo предложила исход мягче правила",
        explanation=(
            "Политика решений ответила менее осторожно, чем жёсткое правило: например, "
            "обычная карточка вместо предупреждения. Слой решений отбросил этот ответ и "
            "оставил исход правила, так что человек защищён, но версия политики сломана — её "
            "надо снять, пока она в силе."
        ),
        condition=NeverIncreases(UNSAFE_OUTCOMES),
    ),
    InvariantMonitor(
        name="decision_outcome_outside_bounds",
        invariant="ADR 0069",
        summary="Решение Leo вышло не из ответа Jev в срок",
        explanation=(
            "Слой решений поймал изменённый исход, который пришёл не как ответ Jev в срок от "
            "действующей версии — например, голосовое «да» из тени или запасного правила. Он "
            "оставил исход правила: без согласия на экране действие не выполнено. Это граница "
            "исключения для голосового подтверждения; найдите путь, который её обошёл."
        ),
        condition=NeverIncreases(OUTSIDE_BOUNDS),
    ),
)

DECISIONS_TRACKED = (
    TrackedLatency(
        LEO_DECISIONS,
        "Ожидание решения: 95 % решений быстрее этой линии",
        "Сколько Leo ждёт решение — от правила до ответа Jev или запасного правила по сроку. "
        "Срок задаёт политика: 350 мс для набора инструментов, 400 мс для карточки, 300 мс "
        "для проверки текста, 800 мс для голосового «да».",
        DECISION_SECONDS,
        (
            ("набор инструментов", 'point="turn.route"'),
            ("карточка", 'point="action.friction"'),
            ("проверка текста", 'point="content.injection"'),
            ("голосовое «да»", 'point="voice.approval"'),
        ),
    ),
)

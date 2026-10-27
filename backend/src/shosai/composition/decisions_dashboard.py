"""Leo's decisions dashboard (decisions plan §3.8): who settles each point, why the rule stood in,
late answers and lost records, in plain Russian. The promises and the time waited are on the
journey's dashboard; reliability per band and cost per day come with the daily pass.
"""

from typing import Any, Final

from shosai.core.observability.grafana import PER_MINUTE, SHARE, Chart, Series, dashboard, row
from shosai.features.decisions.infrastructure.metrics import REQUESTS

POINTS: Final = {
    "turn.route": "набор инструментов",
    "action.friction": "карточка",
    "content.injection": "проверка текста",
    "voice.approval": "голосовое «да»",
}
# Почему решило правило: чаще всего срок, сбой провайдера, нулевое хранение и занятость.
FALLBACK_REASONS: Final = {
    "deadline": "Jev не успел",
    "provider_error": "сбой провайдера",
    "not_zdr": "нет нулевого хранения",
    "busy": "много вызовов разом",
}


def jev_share(point: str) -> str:
    """The share of a point's consulted decisions that Jev settled, judged or later."""
    consulted = f'{REQUESTS}{{point="{point}",reason!~"nothing_to_decide|policy_off"}}'
    settled = f'{REQUESTS}{{point="{point}",source="jev"}}'
    return f"sum(rate({settled}[1h])) / sum(rate({consulted}[1h]))"


def per_minute(selector: str) -> str:
    """A counter's events per minute."""
    return f"sum(rate({selector}[5m])) * 60"


def decisions() -> dict[str, Any]:
    """Who decides, why the rule stood in, what came late or was lost."""
    panels = [
        row("Кто решает"),
        Chart(
            "Доля решений Jev",
            "Из решений, для которых есть политика в силе, — сколько принял Jev, а не "
            "запасное правило. Пусто, пока политики нет: тогда решает правило.",
            SHARE,
            [Series(name, jev_share(point)) for point, name in POINTS.items()],
        ).panel(),
        Chart(
            "Запасное правило: почему",
            "Сколько решений в минуту приняло правило вместо Jev, по причине.",
            PER_MINUTE,
            [
                Series(name, per_minute(f'{REQUESTS}{{source="fallback",reason="{reason}"}}'))
                for reason, name in FALLBACK_REASONS.items()
            ],
        ).panel(),
        row("Опоздания и потери"),
        Chart(
            "Опоздавшие ответы Jev",
            "Ответы, пришедшие после срока решения: Leo уже пошёл по правилу, ответ только "
            "записан для калибровки.",
            PER_MINUTE,
            [
                Series(name, per_minute(f'shosai_decision_late_total{{point="{point}"}}'))
                for point, name in POINTS.items()
            ],
        ).panel(),
        Chart(
            "Голосовые подтверждения",
            "Сколько раз в минуту Jev прочитал ответ человека как ясное «да» зачитанной "
            "карточке — и действие выполнено без экрана.",
            PER_MINUTE,
            [
                Series(
                    "согласия", per_minute('shosai_decision_consents_total{point="voice.approval"}')
                )
            ],
        ).panel(),
        Chart(
            "Потерянные записи решений",
            "Записи решений и их исходов, которые не удалось сохранить в базе дома.",
            PER_MINUTE,
            [Series("записи", per_minute("shosai_decision_records_lost_total"))],
        ).panel(),
    ]
    return dashboard(
        "leo-decisions",
        "Решения Leo: кто решает",
        "Jev или запасное правило, причины, опоздания и потерянные записи.",
        panels,
    )

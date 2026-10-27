"""The AI providers' dashboard (§16.5): calls, failures, latency and spend, in plain Russian.

OpenRouter carries most calls and gets its own row; the four others share charts, one series
each, so no chart holds more than four series.
"""

from typing import Any

from shosai.core.observability.grafana import (
    DOLLARS_PER_HOUR,
    PER_MINUTE,
    SECONDS,
    SERIES_COLORS,
    Chart,
    Panel,
    Series,
    dashboard,
    row,
)
from shosai.core.observability.tiles import Tile

OTHER_PROVIDERS = {
    "openai": "OpenAI",
    "google": "Google",
    "mistral": "Mistral",
}


def calls(provider: str, outcome: str = "") -> str:
    """Calls per minute to a provider; `outcome` narrows to failed ones."""
    failed = ',outcome!="ok"' if outcome else ""
    return f'sum(rate(shosai_ai_calls_total{{provider="{provider}"{failed}}}[5m])) * 60'


def call_p95(provider: str) -> str:
    """The time 95 % of a provider's calls stay under, in seconds."""
    buckets = f'shosai_ai_call_duration_seconds_bucket{{provider="{provider}"}}'
    return f"histogram_quantile(0.95, sum by (le) (rate({buckets}[5m])))"


def spend(provider: str) -> str:
    """A provider's spend in dollars per hour."""
    return f'sum(rate(shosai_ai_cost_microusd_total{{provider="{provider}"}}[1h])) * 3600 / 1e6'


def providers() -> dict[str, Any]:
    """The AI providers: calls, failures, latency, spend."""
    others = OTHER_PROVIDERS.items()
    panels: list[Panel] = [
        Tile(
            "Расход на ИИ за последний час",
            "Сколько долларов стоили все запросы к ИИ за последний час.",
            "sum(increase(shosai_ai_cost_microusd_total[1h])) / 1e6 or vector(0)",
            {
                "unit": "suffix: $",
                "decimals": 2,
                "color": {"mode": "fixed", "fixedColor": SERIES_COLORS[0]},
            },
            (24, 5),
            trend=True,
        ).panel(),
        row("OpenRouter: чат, картинки, расшифровка записей"),
        Chart(
            "Запросы в минуту",
            "Сколько запросов уходит в OpenRouter и сколько из них с ошибкой.",
            PER_MINUTE,
            [
                Series("всего", calls("openrouter")),
                Series("с ошибкой", calls("openrouter", "failed")),
            ],
            width=8,
        ).panel(),
        Chart(
            "Время ответа: 95 % быстрее этой линии",
            "Для потоков — до последнего куска ответа.",
            SECONDS,
            [Series("95 % быстрее", call_p95("openrouter"))],
            width=8,
        ).panel(),
        Chart(
            "Расход",
            "Сколько долларов в час стоят запросы к OpenRouter.",
            DOLLARS_PER_HOUR,
            [Series("OpenRouter", spend("openrouter"))],
            width=8,
        ).panel(),
        row("Живые встречи, перевод, разметка говорящих, распознавание документов"),
        Chart(
            "Запросы в минуту",
            "Сколько запросов уходит к каждому провайдеру.",
            PER_MINUTE,
            [Series(name, calls(key)) for key, name in others],
        ).panel(),
        Chart(
            "Ошибки в минуту",
            "Сколько запросов к каждому провайдеру заканчиваются ошибкой.",
            PER_MINUTE,
            [Series(name, calls(key, "failed")) for key, name in others],
        ).panel(),
        Chart(
            "Время ответа: 95 % быстрее этой линии",
            "У живых сессий — до конца сессии.",
            SECONDS,
            [Series(name, call_p95(key)) for key, name in others],
        ).panel(),
        Chart(
            "Расход",
            "Сколько долларов в час стоят запросы к каждому провайдеру.",
            DOLLARS_PER_HOUR,
            [Series(name, spend(key)) for key, name in others],
        ).panel(),
    ]
    return dashboard("ai-providers", "Провайдеры ИИ", "Запросы, ошибки, скорость и расход.", panels)

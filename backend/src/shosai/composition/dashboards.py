"""Core's dashboards and every dashboard rendered to files (§16.5, F5 plan step 7).

Core owns what no slice owns: the processes of the platform, the two data homes and the AI
providers. Journeys and invariant monitors get theirs from the declarations
(`core/observability/dashboards.py`). Everything the owner reads is plain Russian.
"""

import json
from collections.abc import Sequence
from typing import Any

from shosai.composition.ai_dashboard import providers
from shosai.composition.decisions_dashboard import decisions
from shosai.composition.objectives import declared_rules
from shosai.core.features import FeatureModule
from shosai.core.observability.dashboards import invariants_dashboard, journey_dashboards
from shosai.core.observability.grafana import (
    MEGABYTES,
    MILLISECONDS,
    MINUTES,
    PER_MINUTE,
    PIECES,
    SECONDS,
    SHARE,
    Chart,
    Panel,
    Series,
    dashboard,
    row,
)
from shosai.core.observability.tiles import status

HTTP = "http_server_request_duration_seconds"
ROLES = {
    "api": "API",
    "ws": "живые соединения",
    "workers": "фоновые задачи",
    "scheduler": "планировщик",
}
QUEUES = {"critical": "срочные", "default": "обычные", "bulk": "массовые", "meeting": "встречи"}
HOMES = {"ru": "Россия", "eu": "ЕС"}
P95_NOTE = "Точки — отдельные медленные или неудачные запросы: щелчок открывает их путь и журнал."


def p95(selector: str) -> str:
    """The time 95 % of HTTP requests matching `selector` stay under, in seconds."""
    return f"histogram_quantile(0.95, sum by (le) (rate({HTTP}_bucket{{{selector}}}[5m])))"


def pool_share(home: str) -> str:
    """The busiest process's share of its connections to a home."""
    in_use = f'sum by (instance) (shosai_db_pool_connections{{home="{home}",state="in_use"}})'
    return f'max({in_use} / sum by (instance) (shosai_db_pool_capacity{{home="{home}"}}))'


POOLS = Chart(
    "Занятость подключений к базам",
    "Какая часть подключений к базе занята — у самого загруженного процесса. Пунктир — 70 %: "
    "больше — приходит тикет.",
    SHARE,
    [Series(name, pool_share(home)) for home, name in HOMES.items()],
    limit=0.7,
)


def api_panels() -> list[Panel]:
    """The API's requests per minute and how fast it answers."""
    return [
        row("API: запросы людей"),
        Chart(
            "Запросы в минуту",
            "Сколько запросов к API приходит и сколько из них заканчиваются ошибкой сервера.",
            PER_MINUTE,
            [
                Series("всего", f'sum(rate({HTTP}_count{{job="api"}}[5m])) * 60'),
                Series(
                    "с ошибкой сервера",
                    f'sum(rate({HTTP}_count{{job="api",error_type!=""}}[5m])) * 60',
                ),
            ],
        ).panel(),
        Chart(
            "Время ответа API: 95 % быстрее этой линии",
            P95_NOTE,
            SECONDS,
            [Series("95 % быстрее", p95('job="api"'))],
            exemplars=True,
        ).panel(),
    ]


def role_panels() -> list[Panel]:
    """Every role's event loop lag and memory."""
    return [
        row("Все процессы"),
        Chart(
            "Задержка процессов: 99 % короче этой линии",
            "Насколько процесс опаздывает с работой, потому что занят. Пунктир — 100 мс: "
            "дольше — процесс перегружен или что-то его блокирует.",
            MILLISECONDS,
            [
                Series(
                    name,
                    "histogram_quantile(0.99, sum by (le) (rate("
                    f'shosai_event_loop_lag_seconds_bucket{{job="{role}"}}[5m]))) * 1000',
                )
                for role, name in ROLES.items()
            ],
            limit=100,
        ).panel(),
        Chart(
            "Память процессов",
            "Сколько памяти занимают все процессы каждой роли вместе.",
            MEGABYTES,
            [
                Series(name, f'sum(process_resident_memory_bytes{{job="{role}"}}) / 1048576')
                for role, name in ROLES.items()
            ],
        ).panel(),
    ]


def task_panels() -> list[Panel]:
    """Background tasks: outcomes, the queues' oldest task and depth, the pools."""
    return [
        row("Фоновые задачи"),
        Chart(
            "Фоновые задачи в минуту",
            "Сколько задач выполнилось, ушло на повтор после ошибки и было отложено до ручного "
            "разбора.",
            PER_MINUTE,
            [
                Series(name, f'sum(rate(shosai_task_runs_total{{outcome="{outcome}"}}[5m])) * 60')
                for outcome, name in (
                    ("succeeded", "выполнено"),
                    ("retried", "на повтор"),
                    ("dead_lettered", "отложено"),
                )
            ],
        ).panel(),
        Chart(
            "Самая старая задача в очереди",
            "Сколько минут ждёт самая старая задача каждой очереди. Пунктир — 10 минут: дольше — "
            "приходит тикет.",
            MINUTES,
            [
                Series(name, f'max(shosai_task_queue_oldest_age_seconds{{queue="{queue}"}}) / 60')
                for queue, name in QUEUES.items()
            ],
            limit=10,
        ).panel(),
        Chart(
            "Задач в очереди",
            "Сколько задач ждёт выполнения в каждой очереди.",
            PIECES,
            [
                Series(name, f'max(shosai_task_queue_depth{{queue="{queue}"}})')
                for queue, name in QUEUES.items()
            ],
        ).panel(),
        # Ход ждёт секунды, а не минуты: у очереди ходов Leo своя шкала (AG-D12).
        Chart(
            "Ход Leo ждёт воркер",
            "Сколько секунд ждёт самый старый ход Leo, которого ещё не взял воркер ходов: эти "
            "секунды человек видит до первого слова ответа.",
            SECONDS,
            [Series("ходы Leo", 'max(shosai_task_queue_oldest_age_seconds{queue="agent"})')],
        ).panel(),
        POOLS.panel(),
    ]


def processes() -> dict[str, Any]:
    """Processes of the plane: the API, every role, background tasks, queues, pools."""
    return dashboard(
        "process-roles",
        "Процессы сервера",
        "Как работают процессы сервера и их очереди.",
        [*api_panels(), *role_panels(), *task_panels()],
    )


def homes() -> dict[str, Any]:
    """The two data homes: reachable, how far, how fast for people, pools, the outbox."""
    reachable = [
        status(
            f"База данных: {name} — не отвечает",
            "Проверка соединения изнутри сервера. «Да ✗» — люди этого дома получают ошибки.",
            f'1 - (max(probe_success{{probe="home_database",home="{home}"}}) or vector(0))',
            size=(12, 5),
        )
        for home, name in HOMES.items()
    ]
    panels: list[Panel] = [
        *reachable,
        Chart(
            "Время соединения с базой",
            "Сколько занимает соединение сервера с базой. Россия дальше от сервера в ЕС, поэтому "
            "там дольше. Пунктир — 250 мс: дольше — приходит тикет.",
            MILLISECONDS,
            [
                Series(
                    name,
                    f'max(probe_duration_seconds{{probe="home_database",home="{home}"}}) * 1000',
                )
                for home, name in HOMES.items()
            ],
            limit=250,
        ).panel(),
        Chart(
            "Скорость кабинета: 95 % ответов быстрее этой линии",
            "Для людей, чьи данные хранятся в России и в ЕС. Пунктир — обещанные 0,3 секунды. "
            + P95_NOTE,
            SECONDS,
            [Series(name, p95(f'home="{home}"')) for home, name in HOMES.items()],
            limit=0.3,
            exemplars=True,
        ).panel(),
        POOLS.panel(),
        Chart(
            "Самое старое неотправленное внутреннее сообщение",
            "Сколько минут ждёт отправки самое старое внутреннее сообщение каждой базы. "
            "Пунктир — 5 минут: дольше — приходит срочное сообщение.",
            MINUTES,
            [
                Series(name, f'max(shosai_outbox_oldest_age_seconds{{home="{home}"}}) / 60')
                for home, name in HOMES.items()
            ],
            limit=5,
        ).panel(),
    ]
    return dashboard(
        "data-homes",
        "Базы данных в России и в ЕС",
        "Доступность и скорость двух баз, где хранятся данные людей.",
        panels,
    )


def rendered_dashboards(features: Sequence[FeatureModule]) -> dict[str, str]:
    """File name → JSON of every dashboard: core's, each journey's, the invariant monitors'."""
    owners = declared_rules(features).values()
    objectives = [slo for owner in owners for slo in owner.objectives]
    monitors = [monitor for owner in owners for monitor in owner.monitors]
    tracked = [latency for feature in features for latency in feature.tracked]
    boards = {
        **journey_dashboards(objectives, tracked),
        "invariant-monitors": invariants_dashboard(monitors),
        "process-roles": processes(),
        "data-homes": homes(),
        "ai-providers": providers(),
        "leo-decisions": decisions(),
    }
    return {
        f"{uid}.json": json.dumps(board, indent=2, ensure_ascii=False) + "\n"
        for uid, board in sorted(boards.items())
    }

"""Core's objectives and invariant monitors, and every owner's rules (§16.3, §16.4).

Core owns what no slice owns: the cabinet API's read latency and the monitors of the
platform's own machinery — unknown tasks, stale outbox, dead letters, provider calls
without a cost row. Each slice declares its own on its `FeatureModule`.
"""

from collections.abc import Mapping, Sequence

from shosai.core.features import FeatureModule
from shosai.core.observability.objectives import (
    AlertClass,
    InvariantMonitor,
    LatencyRatio,
    NeverIncreases,
    ServiceLevelObjective,
    StaysAtMost,
)
from shosai.core.observability.rule_files import OwnerRules
from shosai.core.web.http_metrics import DURATION_METRIC

CORE = "core"
# Порог цели задержки §16.3 — граница корзины HTTP-гистограммы (core/web/http_metrics.py).
LATENCY_THRESHOLD = "0.3"
# Чтения кабинета — GET человека, вошедшего в свой дом: у анонимных запросов home пуст.
CABINET_READS = 'http_request_method="GET",home="{home}"'

CORE_OBJECTIVES: tuple[ServiceLevelObjective, ...] = (
    ServiceLevelObjective(
        name="cabinet_reads_latency_eu",
        journey="cabinet_api",
        summary="Кабинет открывается медленно у людей, чьи данные хранятся в ЕС",
        promise="у людей, чьи данные хранятся в ЕС, 95 % страниц и данных кабинета загружаются "
        "быстрее 0,3 секунды",
        target=0.95,
        indicator=LatencyRatio(DURATION_METRIC, CABINET_READS.format(home="eu"), LATENCY_THRESHOLD),
    ),
    # Российский дом — отслеживается, не будит (§16.3, §20): данные в 180 мс от плоскости.
    ServiceLevelObjective(
        name="cabinet_reads_latency_ru",
        journey="cabinet_api",
        summary="Кабинет открывается медленно у людей, чьи данные хранятся в России",
        promise="у людей, чьи данные хранятся в России, 95 % страниц и данных кабинета "
        "загружаются быстрее 0,3 секунды",
        target=0.95,
        indicator=LatencyRatio(DURATION_METRIC, CABINET_READS.format(home="ru"), LATENCY_THRESHOLD),
        alerting=AlertClass.TICKET,
    ),
)

CORE_MONITORS: tuple[InvariantMonitor, ...] = (
    InvariantMonitor(
        name="unknown_task_dropped",
        invariant="§14 rule 9",
        summary="Фоновая работа потерялась: сервер получил задачу, которую не умеет выполнять",
        explanation=(
            "Сервер выбросил фоновую задачу, потому что ни один обработчик её не знает. "
            "Обычно так бывает, когда новая версия выложена в неправильном порядке. Работа "
            "этой задачи — письмо, обработка, синхронизация — не выполнена."
        ),
        condition=NeverIncreases("shosai_task_unknown_total"),
    ),
    InvariantMonitor(
        name="outbox_event_stale",
        invariant="events delivered",
        summary="Внутренние сообщения сервиса застряли больше чем на 5 минут",
        explanation=(
            "Когда в сервисе что-то происходит (например, человек зарегистрировался), об этом"
            " рассылается внутреннее сообщение, и по нему выполняется связанная работа. "
            "Сейчас такое сообщение ждёт отправки дольше 5 минут — связанная работа не "
            "происходит."
        ),
        condition=StaysAtMost("shosai_outbox_oldest_age_seconds", 300),
    ),
    InvariantMonitor(
        name="dead_letter_present",
        invariant="inv-8",
        summary="Фоновые задачи не выполнились и отложены до ручного разбора",
        explanation=(
            "Задача пять раз подряд закончилась ошибкой, и сервер перестал её повторять. Сама"
            " она уже не выполнится: её нужно разобрать и перезапустить вручную."
        ),
        condition=StaysAtMost("shosai_task_dead_letter_entries"),
    ),
    InvariantMonitor(
        name="provider_call_without_cost_row",
        invariant="inv-9",
        summary="Запрос к ИИ прошёл, но его стоимость не записалась",
        explanation=(
            "Сервис обратился к провайдеру ИИ, а запись о стоимости этого обращения не "
            "сохранилась. Наши расходы на ИИ сейчас занижены."
        ),
        condition=NeverIncreases("shosai_ai_calls_without_cost_row_total"),
    ),
    InvariantMonitor(
        name="billed_call_without_cost_row",
        invariant="inv-9",
        summary="Провайдер ИИ насчитал запросы, которых нет в наших расходах",
        explanation=(
            "Ежечасная сверка нашла обращения к ИИ, за которые провайдер берёт деньги, а у "
            "нас о них нет записей. Наши расходы на ИИ занижены."
        ),
        condition=StaysAtMost("shosai_ai_cost_rows_missing"),
    ),
)


def declared_rules(features: Sequence[FeatureModule]) -> Mapping[str, OwnerRules]:
    """Every owner's declarations: core's and each slice's."""
    owners = {CORE: OwnerRules(CORE_OBJECTIVES, CORE_MONITORS)}
    for feature in features:
        owners[feature.name] = OwnerRules(feature.objectives, feature.monitors)
    return owners

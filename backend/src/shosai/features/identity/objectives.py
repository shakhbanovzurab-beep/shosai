"""Sign-in's objectives (§16.3) and identity's invariant monitors (§16.4).

Availability counts every sign-in route; latency counts successful password sign-ins, the
only ones that know the person's home (`note_caller`), per home: the EU's pages, the Russian
home's is measured separately as a ticket. The monitors guard inv-1 — every address in
the directory leads to an account in its home — and nfr-13 — nothing of an erased person
is left behind.
"""

from shosai.core.observability.objectives import (
    AlertClass,
    EventRatio,
    InvariantMonitor,
    Journey,
    LatencyRatio,
    NeverIncreases,
    ServiceLevelObjective,
    StaysAtMost,
)
from shosai.core.web.http_metrics import DURATION_METRIC

SIGN_IN_ROUTES = (
    "/v1/auth/login|/v1/auth/email/verify|/v1/auth/social/complete|/v1/auth/desktop/exchange"
)
SIGN_IN = f'http_route=~"{SIGN_IN_ROUTES}"'
SIGN_IN_JOURNEY = Journey("sign_in", "Вход в аккаунт")
LATENCY_THRESHOLD = "0.3"

SIGN_IN_OBJECTIVES = (
    ServiceLevelObjective(
        name="sign_in_availability",
        journey=SIGN_IN_JOURNEY,
        summary="Люди не могут войти в аккаунт: вход заканчивается ошибкой",
        promise="вход в аккаунт срабатывает без ошибки с нашей стороны в 99,9 % случаев",
        target=0.999,
        indicator=EventRatio(
            total=f"{DURATION_METRIC}_count{{{SIGN_IN}}}",
            bad=f'{DURATION_METRIC}_count{{{SIGN_IN},error_type!=""}}',
        ),
    ),
    ServiceLevelObjective(
        name="sign_in_latency_eu",
        journey=SIGN_IN_JOURNEY,
        summary="Вход в аккаунт работает медленно у людей, чьи данные хранятся в ЕС",
        promise="у людей, чьи данные хранятся в ЕС, 95 % входов занимают меньше 0,3 секунды",
        target=0.95,
        indicator=LatencyRatio(DURATION_METRIC, f'{SIGN_IN},home="eu"', LATENCY_THRESHOLD),
    ),
    ServiceLevelObjective(
        name="sign_in_latency_ru",
        journey=SIGN_IN_JOURNEY,
        summary="Вход в аккаунт работает медленно у людей, чьи данные хранятся в России",
        promise="у людей, чьи данные хранятся в России, 95 % входов занимают меньше 0,3 секунды",
        target=0.95,
        indicator=LatencyRatio(DURATION_METRIC, f'{SIGN_IN},home="ru"', LATENCY_THRESHOLD),
        alerting=AlertClass.TICKET,
    ),
)

IDENTITY_MONITORS = (
    InvariantMonitor(
        name="directory_entry_without_account",
        invariant="inv-1",
        summary="В каталоге есть адреса, за которыми нет аккаунта",
        explanation=(
            "Каталог говорит, в каком доме живёт аккаунт с этой почтой, но в том доме "
            "аккаунта нет уже больше 10 минут. Человек с этой почтой не может ни войти, ни "
            "зарегистрироваться заново."
        ),
        condition=StaysAtMost("shosai_identity_directory_orphans"),
    ),
    InvariantMonitor(
        name="erasure_leftovers",
        invariant="nfr-13",
        summary="После удаления аккаунта остались данные человека",
        explanation=(
            "Проверка после удаления аккаунта нашла данные этого человека: строки, файлы "
            "или доступы к внешним сервисам. Человек попросил удалить всё, а удалено не всё."
        ),
        condition=NeverIncreases("shosai_identity_erasure_leftovers_total"),
    ),
)

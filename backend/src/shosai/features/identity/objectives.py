"""Sign-in's objectives (§16.3): sign-ins end without a server error, and end fast.

Availability counts every sign-in route; latency counts successful password sign-ins, the
only ones that know the person's home (`note_caller`), per home: the EU's pages, the Russian
home's is measured separately as a ticket.
"""

from shosai.core.observability.objectives import (
    AlertClass,
    EventRatio,
    LatencyRatio,
    ServiceLevelObjective,
)
from shosai.core.web.http_metrics import DURATION_METRIC

SIGN_IN_ROUTES = (
    "/v1/auth/login|/v1/auth/email/verify|/v1/auth/social/complete|/v1/auth/desktop/exchange"
)
SIGN_IN = f'http_route=~"{SIGN_IN_ROUTES}"'
LATENCY_THRESHOLD = "0.3"

SIGN_IN_OBJECTIVES = (
    ServiceLevelObjective(
        name="sign_in_availability",
        journey="sign_in",
        summary="Входы завершаются ошибкой сервера чаще, чем позволяет цель",
        target=0.999,
        indicator=EventRatio(
            total=f"{DURATION_METRIC}_count{{{SIGN_IN}}}",
            bad=f'{DURATION_METRIC}_count{{{SIGN_IN},error_type!=""}}',
        ),
    ),
    ServiceLevelObjective(
        name="sign_in_latency_eu",
        journey="sign_in",
        summary="Входы в доме ЕС дольше 300 мс чаще, чем позволяет цель",
        target=0.95,
        indicator=LatencyRatio(DURATION_METRIC, f'{SIGN_IN},home="eu"', LATENCY_THRESHOLD),
    ),
    ServiceLevelObjective(
        name="sign_in_latency_ru",
        journey="sign_in",
        summary="Входы в российском доме дольше 300 мс чаще, чем позволяет цель",
        target=0.95,
        indicator=LatencyRatio(DURATION_METRIC, f'{SIGN_IN},home="ru"', LATENCY_THRESHOLD),
        alerting=AlertClass.TICKET,
    ),
)

"""The alerting slice as composition sees it (F5 plan §3.11).

No tables and no routes: two subscriptions and one task. Alertmanager's client opens and
closes with the process; every role builds it, since every role registers every task.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.features.alerting.channels.subscriptions import BusinessAlerts
from shosai.features.alerting.channels.tasks import task_handlers
from shosai.features.alerting.infrastructure.alertmanager import open_alertmanager
from shosai.features.alerting.infrastructure.metrics import AlertingMetrics
from shosai.features.alerting.settings import AlertingSettings


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """Open Alertmanager's client; build the subscriptions and the delivery task."""
    settings = services.settings.features.get(AlertingSettings)
    site = str(services.settings.email.public_base_url)
    alerts = BusinessAlerts(services.tasks, site, enabled=settings.alerting_enabled)
    metrics = AlertingMetrics(services.registry)
    async with open_alertmanager(settings.alerting_alertmanager_url, metrics) as alertmanager:
        yield FeatureParts(
            task_handlers=task_handlers(alertmanager, services.settings.environment),
            subscriptions=alerts.subscriptions(),
        )


ALERTING = FeatureModule(name="alerting", build=build, settings=(AlertingSettings,))

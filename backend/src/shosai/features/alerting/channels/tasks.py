"""The task that hands one business alert to Alertmanager, outside any transaction.

A subscription queues it in the delivery's transaction (§14 rule 1: no external call
there). Alertmanager unreachable or failing earns another delivery, five in all; then
the task is dead-lettered, and the dead-letter monitor pages (§16.4). A delivery that
repeats after Alertmanager took the alert posts the same alert again, which Alertmanager
merges by its labels.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, Final
from uuid import UUID

from shosai.core.config.values import Environment
from shosai.core.observability.log_context import LogFields
from shosai.core.observability.rule_files import RUNBOOK
from shosai.core.tasks.declaration import MAX_DELIVERIES, RetryPolicy, TaskDeclaration, TaskHandler
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.alerting.domain.alerts import BusinessAlert
from shosai.features.alerting.infrastructure.alertmanager import (
    ALERT_LIFETIME,
    Alertmanager,
    AlertmanagerUnavailableError,
    PostedAlert,
)

# Как окружение называется в сообщении: так же, как во внешней метке Prometheus.
ENVIRONMENT_LABELS: Final = {
    Environment.DEVELOPMENT: "local",
    Environment.STAGING: "staging",
    Environment.PRODUCTION: "production",
}


class AlertPayload(HomeTaskPayload):
    """One business alert on its way: the event's id and time, and what the owner reads."""

    event_id: UUID
    occurred_at: datetime
    alert: BusinessAlert

    def log_fields(self) -> LogFields:
        """The home, the account and the event."""
        fields = super().log_fields()
        fields["event_id"] = self.event_id
        return fields


POST_ALERT: Final = TaskDeclaration(
    name="alerting.post_alert",
    queue=TaskQueue.DEFAULT,
    payload=AlertPayload,
    deadline=timedelta(seconds=30),
    retry=RetryPolicy(max_deliveries=MAX_DELIVERIES, retry_on=(AlertmanagerUnavailableError,)),
)


def posted_alert(payload: AlertPayload, environment: Environment, now: datetime) -> PostedAlert:
    """The alert with its labels: the event's id makes a repeat the same alert."""
    alert = payload.alert
    return PostedAlert(
        labels={
            "alertname": alert.name,
            "severity": alert.severity.value,
            "kind": alert.kind,
            "event_id": str(payload.event_id),
            "home": payload.home.value,
            "environment": ENVIRONMENT_LABELS[environment],
        },
        annotations={
            "summary": alert.summary,
            "description": alert.description,
            "runbook": f"{RUNBOOK}#{alert.runbook}",
            "admin_card": alert.admin_card,
        },
        starts_at=payload.occurred_at,
        ends_at=now + ALERT_LIFETIME,
    )


def task_handlers(
    alertmanager: Alertmanager, environment: Environment
) -> tuple[TaskHandler[Any], ...]:
    """The delivery task bound to the process's Alertmanager client."""

    async def post_alert(payload: AlertPayload) -> None:
        await alertmanager.post(posted_alert(payload, environment, datetime.now(UTC)))

    return (TaskHandler(POST_ALERT, post_alert),)

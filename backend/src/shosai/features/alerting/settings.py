"""Alerting's settings (`ALERTING_*`), documented in `.env.example` section 2."""

from pydantic import HttpUrl

from shosai.core.config.sections import SettingsSection


class AlertingSettings(SettingsSection):
    """Whether business events reach Alertmanager, and where it listens."""

    # Выключено — событие принимается и помечается, но оповещение не уходит (запись в журнале).
    # На staging и в production включено: без него тикеты о расходе и уведомления теряются.
    alerting_enabled: bool = False
    # Alertmanager стека наблюдаемости; роли и стек — в одной сети Compose.
    alerting_alertmanager_url: HttpUrl = HttpUrl("http://alertmanager:9093")

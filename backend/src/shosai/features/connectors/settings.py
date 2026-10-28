"""Connectors' settings (`CONNECTORS_*`), documented in `.env.example` section 2.

Each provider's OAuth application adds its client id and secret with the provider's step;
until then the provider is not configured and its apps are not offered (CN-D4).
"""

from pydantic import HttpUrl

from shosai.core.config.sections import SettingsSection


class ConnectorsSettings(SettingsSection):
    """Where providers return the browser to; the OAuth applications come with their steps."""

    # Публичный адрес API для redirect_uri провайдеров; пусто — адрес писем (EMAIL_PUBLIC_BASE_URL).
    connectors_public_base_url: HttpUrl | None = None

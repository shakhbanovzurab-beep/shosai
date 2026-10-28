"""Connectors' settings (`CONNECTORS_*`), documented in `.env.example` section 2.

Each provider's OAuth application adds its client id and secret with the provider's step;
until then the provider is not configured and its apps are not offered (CN-D4). An
application is configured by both values or by neither: one of them alone is refused at
start rather than leaving the apps silently unoffered. A Google project in Testing gives
seven-day refresh tokens; "Shosai Mail" stays in Testing until CASA has a budget (CN-D5).
"""

from typing import Self

from pydantic import HttpUrl, SecretStr, model_validator

from shosai.core.config.sections import SettingsSection


class ConnectorsSettings(SettingsSection):
    """Where providers return the browser to, and the OAuth applications configured."""

    # Публичный адрес API для redirect_uri провайдеров; пусто — адрес писем (EMAIL_PUBLIC_BASE_URL).
    connectors_public_base_url: HttpUrl | None = None
    # Приложение 3LO в консоли разработчика Atlassian: Jira и Confluence.
    connectors_atlassian_client_id: str | None = None
    connectors_atlassian_client_secret: SecretStr | None = None
    # Основной проект Google: Календарь и Диск; на стенде — в статусе Testing.
    connectors_google_client_id: str | None = None
    connectors_google_client_secret: SecretStr | None = None
    connectors_google_testing: bool = False
    # Проект «Shosai Mail»: Gmail, в статусе Testing до бюджета на CASA.
    connectors_google_mail_client_id: str | None = None
    connectors_google_mail_client_secret: SecretStr | None = None
    connectors_google_mail_testing: bool = True

    @model_validator(mode="after")
    def applications_whole(self) -> Self:
        """Refuse an application with its id and no secret, or the other way round."""
        pairs = {
            "atlassian": (
                self.connectors_atlassian_client_id, self.connectors_atlassian_client_secret
            ),
            "google": (self.connectors_google_client_id, self.connectors_google_client_secret),
            "google_mail": (
                self.connectors_google_mail_client_id, self.connectors_google_mail_client_secret
            ),
        }  # fmt: skip
        for name, (client_id, secret) in pairs.items():
            if (client_id is None) != (secret is None):
                message = f"приложение {name}: нужны и CLIENT_ID, и CLIENT_SECRET"
                raise ValueError(message)
        return self

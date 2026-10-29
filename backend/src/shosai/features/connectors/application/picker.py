"""Google's Picker in the cabinet (CN-D5, plan §3.7): the browser's own short `drive.file`
token comes from Google Identity Services, so Shosai's server never hands a token to the
browser; it gives only the Picker's browser key, the project's number, the main project's
OAuth client id (public, as every browser sign-in's) and the account to pick from, so the
person chooses with the account they connected."""

from dataclasses import dataclass
from http import HTTPStatus

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.contracts import NotConnectedError
from shosai.features.connectors.domain.catalogue import App
from shosai.features.connectors.infrastructure.store.connection_reads import bindings
from shosai.features.connectors.infrastructure.store.records import ConnectionRecord


class PickerUnavailableError(AppError):
    """This deployment has no Picker key or project number."""

    def __init__(self) -> None:
        super().__init__("picker_unavailable", HTTPStatus.SERVICE_UNAVAILABLE)


@dataclass(frozen=True, slots=True)
class PickerSetup:
    """The Picker's browser key and the main project's number, as the deployment set them."""

    api_key: str | None
    project_number: str | None
    client_id: str | None


@dataclass(frozen=True, slots=True)
class PickerConfig:
    """What the cabinet opens the Picker with."""

    developer_key: str
    app_id: str
    client_id: str
    login_hint: str | None


class DrivePicker:
    """The Picker's setup for a person's connected Drive."""

    def __init__(self, transactions: HomeTransactions, setup: PickerSetup) -> None:
        self._transactions = transactions
        self._setup = setup

    async def config(self, scope: TenancyScope) -> PickerConfig:
        """The Picker's setup; `not_connected` without a connected Drive."""
        key, project, client = (
            self._setup.api_key, self._setup.project_number, self._setup.client_id
        )  # fmt: skip
        if key is None or project is None or client is None:
            raise PickerUnavailableError
        if scope.user_id is None:
            raise NotConnectedError
        async with self._transactions.begin(scope, read_only=True) as session:
            found = await bindings(
                session, ConnectionRecord.user_id == scope.user_id,
                ConnectionRecord.org_id.is_(None), ConnectionRecord.app == App.GOOGLE_DRIVE.value,
            )  # fmt: skip
        if not found:
            raise NotConnectedError
        return PickerConfig(key, project, client, found[0].view.account_label)

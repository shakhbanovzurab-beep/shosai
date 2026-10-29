"""The connectors slice as composition sees it (connectors plan §3.1, ADR 0075).

Step 1 published the contracts and the domain. Step 2 the tables in each home — grants, their
secrets, the apps on them — with row-level security that keeps a personal row its person's
alone, and the handler of what connectors holds of a person. Step 3 the OAuth core: a flow
started by `POST /v1/connectors/{app}/authorize` with PKCE, a one-time state in Valkey and a
browser binder, finished at `GET /v1/connectors/oauth/{provider}/callback` into a grant, its
encrypted secrets and the app on it. It also brings a workspace's installations for chats
and the draft's callback paths, which answer an expired authorization. Step 4 the grant's
lifecycle: one refresh at a time on a lease and a generation, keep-alive refreshes and
revocations swept from due rows, a disconnect that revokes on the last app, the provider's
revocation on erasure, the weekly key pass, a deleted workspace's installations, and three
invariant monitors. Step 5 the provider transport behind `PROVIDER_ACCESS`: a session that
injects and refreshes the token, keeps the provider's quotas, concurrency and `Retry-After`
for every process, opens a provider's breaker only on its own failures, and retries reads.
Step 6 the cabinet's routes — the list, a disconnect, connecting by a given secret, a scope
picker's browse — and `CONNECTIONS` for consumers. Step 8 Atlassian: the Jira grant at its
registered `/v1/jira/oauth/callback`, its sites, the weekly personal data report, and the
quota alert. Step 9 Google's two applications. Step 10 the `CALENDARS` port with Google
Calendar. Step 11 the `MAILBOXES` port with Gmail, offered to testers until CASA. Step 12
`FILE_SOURCES` and the scope picker over Google Drive's `drive.file`, and the Picker's setup.
Step 13 Microsoft's Entra application and Outlook Calendar on Graph.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.crypto.key_ring import FernetKeyRing
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.core.ports.keys import PortBinding
from shosai.features.connectors.application.account_data import (
    ACCOUNT_DATA,
    ConnectorsAccountData,
)
from shosai.features.connectors.application.atlassian_accounts import (
    AtlassianAccounts,
    ReportTools,
)
from shosai.features.connectors.application.authorize import Authorizer, AuthorizeTools
from shosai.features.connectors.application.cabinet_list import CabinetConnectors
from shosai.features.connectors.application.calendars import ConnectorCalendars
from shosai.features.connectors.application.callback import CallbackTools, Completer
from shosai.features.connectors.application.credentials import Credentials, CredentialTools
from shosai.features.connectors.application.disconnect import Disconnector
from shosai.features.connectors.application.file_sources import ConnectorFileSources
from shosai.features.connectors.application.grant_tokens import GrantTokens, TokenTools
from shosai.features.connectors.application.installation_audit import InstallationAudit
from shosai.features.connectors.application.installations import WorkspaceInstallations
from shosai.features.connectors.application.key_rotation import KeyRotation
from shosai.features.connectors.application.lifecycle_sweeps import DueGrants
from shosai.features.connectors.application.mailboxes import ConnectorMailboxes
from shosai.features.connectors.application.offers import GmailAccess, Offers
from shosai.features.connectors.application.picker import DrivePicker, PickerSetup
from shosai.features.connectors.application.provider_access import ConnectorProviderAccess
from shosai.features.connectors.application.registry import ConnectorRegistry
from shosai.features.connectors.application.resources import Resources
from shosai.features.connectors.application.revocation import GrantRevoker, RevokeTools
from shosai.features.connectors.channels.http.connect_routes import build_connect_router
from shosai.features.connectors.channels.http.connector_routes import build_connector_router
from shosai.features.connectors.channels.http.picker_routes import build_picker_router
from shosai.features.connectors.channels.subscriptions import subscriptions
from shosai.features.connectors.channels.tasks import (
    DUE_SOURCES,
    PERIODIC_JOBS,
    connectors_task_handlers,
)
from shosai.features.connectors.contracts import CONNECTIONS, INSTALLATIONS, PROVIDER_ACCESS
from shosai.features.connectors.contracts.calendars import CALENDARS
from shosai.features.connectors.contracts.events import CONNECTOR_EVENTS
from shosai.features.connectors.contracts.files import FILE_SOURCES
from shosai.features.connectors.contracts.mailboxes import MAILBOXES
from shosai.features.connectors.domain.catalogue import App
from shosai.features.connectors.infrastructure.metrics import ConnectorsMetrics
from shosai.features.connectors.infrastructure.oauth.flow_store import FlowStore
from shosai.features.connectors.infrastructure.providers.base import ProviderRegistry
from shosai.features.connectors.infrastructure.providers.configured import configured_clients
from shosai.features.connectors.infrastructure.providers.gmail import Gmail
from shosai.features.connectors.infrastructure.providers.google_calendar import GoogleCalendar
from shosai.features.connectors.infrastructure.providers.google_drive import (
    GoogleDrive,
    GoogleDriveResources,
)
from shosai.features.connectors.infrastructure.providers.outlook_calendar import OutlookCalendar
from shosai.features.connectors.infrastructure.store.records import CONNECTOR_MODELS
from shosai.features.connectors.infrastructure.transport.guards import ProviderGuards
from shosai.features.connectors.infrastructure.transport.http_client import (
    open_connectors_http,
)
from shosai.features.connectors.infrastructure.transport.session import SessionParts
from shosai.features.connectors.objectives import MONITORS
from shosai.features.connectors.settings import ConnectorsSettings


def capability_ports(
    access: ConnectorProviderAccess, drive: GoogleDrive
) -> tuple[PortBinding[Any], ...]:
    """The capability ports, each with the adapters of the providers built so far."""
    return (
        CALENDARS.bind(
            ConnectorCalendars(
                access,
                {
                    App.GOOGLE_CALENDAR: GoogleCalendar(),
                    App.OUTLOOK_CALENDAR: OutlookCalendar(),
                },
            )
        ),
        MAILBOXES.bind(ConnectorMailboxes(access, {App.GMAIL: Gmail()})),
        FILE_SOURCES.bind(ConnectorFileSources(access, {App.GOOGLE_DRIVE: drive})),
    )


def picker_setup(settings: ConnectorsSettings) -> PickerSetup:
    """Google Picker's browser key, project number and the main project's OAuth client id."""
    return PickerSetup(
        settings.connectors_google_picker_api_key,
        settings.connectors_google_project_number,
        settings.connectors_google_client_id,
    )


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """Connectors' parts for this process."""
    settings = services.settings.features.get(ConnectorsSettings)
    public = settings.connectors_public_base_url or services.settings.email.public_base_url
    base_url = str(public).rstrip("/")
    crypto = services.settings.crypto
    keys = FernetKeyRing.from_settings(crypto) if crypto.fernet_key is not None else None
    registry = ProviderRegistry(configured_clients(settings))
    flows, audit = FlowStore(services.valkey), InstallationAudit(services.ports)
    metrics = ConnectorsMetrics(services.registry)
    gmail = GmailAccess(
        settings.connectors_gmail_public, frozenset(settings.connectors_gmail_tester_ids)
    )
    offers = Offers(services.ports, registry, gmail)
    async with open_connectors_http() as http:
        authorize = AuthorizeTools(offers, registry, flows, base_url, sealing=keys is not None)
        authorizer = Authorizer(services.transactions, authorize)
        completer = Completer(
            services.transactions,
            CallbackTools(flows, registry, http, keys, services.outbox, audit, base_url),
        )
        tokens = GrantTokens(
            services.transactions, TokenTools(registry, http, keys, services.outbox, metrics)
        )
        revoker = GrantRevoker(services.transactions, RevokeTools(registry, http, keys, metrics))
        rotation = KeyRotation(
            services.transactions, keys, rotating=bool(crypto.fernet_keys_previous),
            metrics=metrics,
        )  # fmt: skip
        accounts = AtlassianAccounts(
            services.transactions, ReportTools(tokens, http, services.outbox, metrics)
        )
        lifecycle = (DueGrants(services.transactions), tokens, revoker, rotation, accounts)
        guards = ProviderGuards(services.valkey, services.rate_limiter)
        tracer = services.tracer_provider.get_tracer("shosai.connectors")
        access = ConnectorProviderAccess(
            services.transactions, registry, SessionParts(tokens, guards, http, metrics, tracer)
        )
        drive = GoogleDrive()
        picker = DrivePicker(services.transactions, picker_setup(settings))
        # Проверки секретов и обзор ресурсов приносят шаги провайдеров.
        cabinet = (
            CabinetConnectors(services.transactions, offers, registry),
            Disconnector(services.transactions, services.outbox, registry),
            Credentials(
                services.transactions, CredentialTools(offers, {}, http, keys, services.outbox)
            ),
            Resources(
                services.transactions, access, {App.GOOGLE_DRIVE: GoogleDriveResources(drive)}
            ),
        )
        limiter = services.rate_limiter
        yield FeatureParts(
            http_routers=(
                build_connect_router((authorizer, completer), services.ports, limiter),
                build_connector_router(cabinet, services.ports, limiter),
                build_picker_router(picker, services.ports),
            ),
            task_handlers=connectors_task_handlers(lifecycle, services.tasks),
            subscriptions=subscriptions(services.outbox),
            due_sources=DUE_SOURCES,
            periodic_jobs=PERIODIC_JOBS,
            provides=(
                ACCOUNT_DATA_HANDLERS.bind(ConnectorsAccountData(services.transactions, revoker)),
                CONNECTIONS.bind(ConnectorRegistry(services.ports)),
                INSTALLATIONS.bind(WorkspaceInstallations(authorizer, audit, services.outbox)),
                PROVIDER_ACCESS.bind(access),
                *capability_ports(access, drive),
            ),
        )


CONNECTORS = FeatureModule(
    name="connectors",
    build=build,
    models=CONNECTOR_MODELS,
    events=CONNECTOR_EVENTS,
    settings=(ConnectorsSettings,),
    account_data=(ACCOUNT_DATA,),
    monitors=MONITORS,
)

"""Settings > Connectors over HTTP, on the transport bench, with test probes and browsers.

Affinity is offered with a probe that accepts the key `good-key`; Google Drive lists
folders through the person's provider session against the API double's `/data`, or its
`/throttle` under the parent `busy`.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
import pytest_asyncio
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.features.connectors.application.cabinet_list import CabinetConnectors
from shosai.features.connectors.application.credentials import (
    Credentials,
    CredentialsRejectedError,
    CredentialTools,
    GivenSecret,
)
from shosai.features.connectors.application.offers import Offers
from shosai.features.connectors.application.resources import Resources
from shosai.features.connectors.channels.http.connect_routes import build_connect_router
from shosai.features.connectors.channels.http.connector_routes import build_connector_router
from shosai.features.connectors.contracts import (
    CONNECTOR_USES,
    ConnectorUses,
    ProviderCall,
    ProviderSession,
)
from shosai.features.connectors.contracts.resources import Resource, ResourcePage, ResourceQuery
from shosai.features.connectors.domain.catalogue import App, AuthKind
from shosai.features.connectors.infrastructure.providers.base import AccountIdentity
from shosai.features.identity.contracts import AUTHENTICATOR
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.people_bench import BearerOfTheTest
from tests.features.connectors.connect_bench import USED
from tests.features.connectors.transport_bench import TransportBench, body_of

GOOD_KEY = "good-key"


@dataclass(frozen=True, slots=True)
class KeyProbe:
    """Affinity's whoami as the test sees it: one key opens the account `team`."""

    @property
    def auth_kind(self) -> AuthKind:
        """An API key."""
        return AuthKind.API_KEY

    async def probe(self, http: httpx.AsyncClient, given: GivenSecret) -> AccountIdentity:
        """The account the key opens, or a refusal."""
        del http
        if given.secret.get_secret_value() != GOOD_KEY:
            raise CredentialsRejectedError
        return AccountIdentity("team", "team@affinity.test", {})


@dataclass(frozen=True, slots=True)
class FolderBrowser:
    """Drive's folders: one call through the session, the answer's header as the name."""

    @property
    def kinds(self) -> frozenset[str]:
        """Folders only."""
        return frozenset({"folder"})

    async def browse(self, session: ProviderSession, query: ResourceQuery) -> ResourcePage:
        """One folder named by what the API saw."""
        path = "/throttle" if query.parent == "busy" else "/data"
        answer = await session.request(ProviderCall("GET", "drive.list", f"https://api.test{path}"))
        folder = Resource(
            id="f-1", name=str(body_of(answer.body)["auth"]), kind=query.kind,
            parent_id=query.parent, has_children=False, url=None,
        )  # fmt: skip
        return ResourcePage((folder,), next_cursor=None)


@dataclass(frozen=True, slots=True)
class CabinetBench:
    """The cabinet's connectors routes in the real shell, and the bench under them."""

    http: httpx.AsyncClient
    transport: TransportBench


@pytest_asyncio.fixture
async def cabinet(transport: TransportBench, valkey: Redis) -> AsyncIterator[CabinetBench]:
    """Both connectors routers at Shosai's public address."""
    connect = transport.lifecycle.connect
    registry, http, outbox = connect.wiring
    ports = PortDirectory()
    ports.install([
        CONNECTOR_USES.bind(ConnectorUses("tests", USED | {App.AFFINITY})),
        AUTHENTICATOR.bind(BearerOfTheTest()),
    ])  # fmt: skip
    offers = Offers(ports, registry)
    transactions = connect.homes.transactions
    tools = CredentialTools(offers, {App.AFFINITY: KeyProbe()}, http, connect.keys, outbox)
    services = (
        CabinetConnectors(transactions, offers, registry), transport.lifecycle.disconnector,
        Credentials(transactions, tools),
        Resources(transactions, transport.access, {App.GOOGLE_DRIVE: FolderBrowser()}),
    )  # fmt: skip
    limiter = RateLimiter(valkey, KeyValueMetrics(CollectorRegistry()))
    routers = (
        build_connect_router((connect.authorizer, connect.completer), ports, limiter),
        build_connector_router(services, ports, limiter),
    )
    app = build_probe_app(extra=routers).app
    async with client_of(app, base_url="https://shosai.test") as client:
        yield CabinetBench(client, transport)

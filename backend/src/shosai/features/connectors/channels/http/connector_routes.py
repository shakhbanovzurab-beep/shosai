"""Settings > Connectors over HTTP (connectors plan §3.7), behind the person's bearer token.

`GET /v1/connectors` lists the offered apps and the person's connections; `DELETE
/v1/connectors/{app}` disconnects one; `POST /v1/connectors/{app}/credentials` connects an
app by a secret the person gives; `GET /v1/connectors/{app}/resources` browses the places of
a connected app for a scope picker. Every route reads only the person's own rows.
"""

from datetime import timedelta
from typing import Annotated, Final

from fastapi import APIRouter, Depends, Path, Query, Response
from pydantic import SecretStr

from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.core.web.rate_limit import rate_limited
from shosai.features.connectors.application.cabinet_list import CabinetConnectors
from shosai.features.connectors.application.credentials import Credentials, GivenSecret
from shosai.features.connectors.application.disconnect import Disconnector
from shosai.features.connectors.application.resources import Resources
from shosai.features.connectors.channels.http.connect_routes import app_of
from shosai.features.connectors.channels.http.connector_views import (
    ConnectorCredentialsIn,
    ConnectorOut,
    ConnectorResourcesOut,
    ConnectorResourcesQuery,
    ConnectorsOut,
    connector_out,
    resources_out,
)
from shosai.features.identity.contracts import Principal, bearer_principal

NO_CONTENT: Final = 204
CREDENTIALS_LIMIT: Final = RateLimit("connector_credentials", 5, timedelta(minutes=1), 5)
RESOURCES_LIMIT: Final = RateLimit("connector_resources", 60, timedelta(minutes=1), 20)
AppSegment = Annotated[str, Path(max_length=32)]


def build_connector_router(
    services: tuple[CabinetConnectors, Disconnector, Credentials, Resources],
    ports: PortDirectory,
    limiter: RateLimiter,
) -> APIRouter:
    """The list, disconnect, credentials and resources routes."""
    cabinet, disconnector, credentials, resources = services
    person = Annotated[Principal, Depends(bearer_principal(ports))]
    router = APIRouter(prefix="/v1/connectors", tags=["connectors"])

    async def subject(principal: person) -> str:
        return str(principal.user_id)

    @router.get("")
    async def list_connectors(principal: person) -> ConnectorsOut:
        """The apps you may connect and the ones you connected."""
        rows = await cabinet.rows(principal.scope())
        return ConnectorsOut(items=[connector_out(row) for row in rows])

    @router.delete("/{app}", status_code=NO_CONTENT)
    async def disconnect(app: AppSegment, principal: person) -> Response:
        """Disconnect an app: everything that used it stops at once."""
        await disconnector.disconnect(principal.scope(), app_of(app))
        return Response(status_code=NO_CONTENT)

    @router.post(
        "/{app}/credentials",
        dependencies=[Depends(rate_limited(limiter, CREDENTIALS_LIMIT, subject))],
    )
    async def connect_with_credentials(
        app: AppSegment, body: ConnectorCredentialsIn, principal: person
    ) -> ConnectorOut:
        """Connect an app by an app password, an API key or a hook URL."""
        chosen = app_of(app)
        given = GivenSecret(SecretStr(body.secret), login=body.login, address=body.address)
        await credentials.connect(principal.scope(), chosen, given)
        return connector_out(await cabinet.row(principal.scope(), chosen))

    @router.get(
        "/{app}/resources", dependencies=[Depends(rate_limited(limiter, RESOURCES_LIMIT, subject))]
    )
    async def browse_resources(
        app: AppSegment, query: Annotated[ConnectorResourcesQuery, Query()], principal: person
    ) -> ConnectorResourcesOut:
        """Places of a connected app: folders, spaces, repositories, channels."""
        page = await resources.browse(principal.scope(), app_of(app), query.query())
        return resources_out(page)

    return router

"""The connect flow over HTTP (connectors plan §3.7).

`POST /v1/connectors/{app}/authorize` starts a person's flow and sets the browser binder;
`GET /v1/connectors/oauth/{provider}/callback` is the redirect URI each OAuth application
registers: it answers 303 with a relative `Location` into the cabinet and clears the binder.
The draft's callback paths answer a flow started on the draft with an expired authorization,
since no such flow exists in Shosai; `/v1/jira/oauth/callback` is Atlassian's registered
redirect URI and finishes Atlassian flows (a draft's state is simply not found there).
"""

from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Annotated, Final, Literal

from fastapi import APIRouter, Cookie, Depends, Path, Query, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from shosai.core.kernel.errors import AppError
from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.core.web.rate_limit import rate_limited
from shosai.features.connectors.application.authorize import (
    COOKIE_NAME,
    COOKIE_PATH,
    Authorizer,
    ConnectRequest,
    cookie_path,
)
from shosai.features.connectors.application.callback import Completer, ProviderAnswer
from shosai.features.connectors.domain.catalogue import App, Provider
from shosai.features.connectors.domain.flows import (
    FlowError,
    Outcome,
    ReturnKind,
    ReturnPathError,
    ReturnTarget,
    callback_location,
)
from shosai.features.connectors.infrastructure.providers.atlassian import ATLASSIAN
from shosai.features.identity.contracts import Principal, bearer_principal

SEE_OTHER: Final = 303
DRAFT_PROVIDERS: Final = ("google", "microsoft", "slack", "notion", "attio", "hubspot")
ATLASSIAN_CALLBACK: Final = cookie_path(ATLASSIAN)
AUTHORIZE_LIMIT: Final = RateLimit("connector_authorize", 10, timedelta(minutes=1), 10)


class ConnectorAuthorizeIn(BaseModel):
    """Where the cabinet wants the browser back: the popup's page or a cabinet path."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    back: Literal["popup", "page"] = Field(default="popup", alias="return")
    return_path: str | None = Field(default=None, max_length=512)


class CallbackQuery(BaseModel):
    """What a provider's redirect carries; unknown parameters are ignored."""

    state: str | None = Field(default=None, max_length=256)
    code: str | None = Field(default=None, max_length=4096)
    error: str | None = Field(default=None, max_length=256)
    error_description: str | None = Field(default=None, max_length=2048)


class ConnectorAuthorizeOut(BaseModel):
    """The provider's consent page and when the flow expires."""

    authorize_url: str
    expires_at: datetime


class UnknownAppError(AppError):
    """An app the catalogue does not know."""

    def __init__(self) -> None:
        super().__init__("unknown_app", HTTPStatus.NOT_FOUND)


def app_of(value: str) -> App:
    """The catalogue's app of a path segment; `unknown_app` for anything else."""
    try:
        return App(value)
    except ValueError:
        raise UnknownAppError from None


class ReturnPathInvalidError(AppError):
    """A return path outside the cabinet."""

    def __init__(self) -> None:
        super().__init__("return_path_invalid", HTTPStatus.UNPROCESSABLE_ENTITY)


def target_of(body: ConnectorAuthorizeIn) -> ReturnTarget:
    """The return target of a request body; `return_path_invalid` outside the cabinet."""
    try:
        if body.back == "page":
            return ReturnTarget(ReturnKind.PAGE, body.return_path or "/app")
        return ReturnTarget(ReturnKind.POPUP)
    except ReturnPathError:
        raise ReturnPathInvalidError from None


def build_connect_router(
    flows: tuple[Authorizer, Completer], ports: PortDirectory, limiter: RateLimiter
) -> APIRouter:
    """The authorize route, the provider callbacks and the draft's callback paths."""
    authorizer, completer = flows
    person = Annotated[Principal, Depends(bearer_principal(ports))]
    router = APIRouter(tags=["connectors"])

    async def subject(principal: person) -> str:
        return str(principal.user_id)

    @router.post(
        "/v1/connectors/{app}/authorize",
        dependencies=[Depends(rate_limited(limiter, AUTHORIZE_LIMIT, subject))],
    )
    async def authorize(
        app: Annotated[str, Path(max_length=32)],
        body: ConnectorAuthorizeIn,
        principal: person,
        response: Response,
    ) -> ConnectorAuthorizeOut:
        """Start connecting an app: the provider's consent page and the browser binder."""
        request = ConnectRequest(
            user_id=principal.user_id, home=principal.home, app=app_of(app), target=target_of(body)
        )
        handoff = await authorizer.begin(request)
        response.headers.append("set-cookie", handoff.cookie.header())
        return ConnectorAuthorizeOut(
            authorize_url=handoff.authorize_url, expires_at=handoff.expires_at
        )

    async def finish(
        provider: Provider, query: CallbackQuery, binder: str | None, path: str = COOKIE_PATH
    ) -> RedirectResponse:
        answer = ProviderAnswer(query.state, query.code, query.error, query.error_description)
        location = await completer.complete(provider, answer, binder)
        redirect = RedirectResponse(location, status_code=SEE_OTHER)
        redirect.delete_cookie(COOKIE_NAME, path=path, secure=True, httponly=True)
        return redirect

    @router.get("/v1/connectors/oauth/{provider}/callback", include_in_schema=False)
    async def callback(
        provider: Provider,
        query: Annotated[CallbackQuery, Query()],
        binder: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
    ) -> RedirectResponse:
        """Finish a flow and send the browser back into the cabinet."""
        return await finish(provider, query, binder)

    @router.get(ATLASSIAN_CALLBACK, include_in_schema=False)
    async def atlassian_callback(
        query: Annotated[CallbackQuery, Query()],
        binder: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
    ) -> RedirectResponse:
        """Finish an Atlassian flow at the redirect URI its application registered."""
        return await finish(Provider.ATLASSIAN, query, binder, ATLASSIAN_CALLBACK)

    async def expired() -> RedirectResponse:
        """A flow that started on the draft: there is nothing to finish."""
        location = callback_location(
            ReturnTarget(ReturnKind.POPUP), None, Outcome.ERROR,
            error=FlowError.AUTHORIZATION_EXPIRED,
        )  # fmt: skip
        return RedirectResponse(location, status_code=SEE_OTHER)

    for name in DRAFT_PROVIDERS:
        router.add_api_route(
            f"/v1/integrations/oauth/{name}/callback", expired, methods=["GET"],
            include_in_schema=False,
        )  # fmt: skip
    return router

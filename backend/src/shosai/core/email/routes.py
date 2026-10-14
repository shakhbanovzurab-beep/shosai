"""The links in mail (F6-C21): `GET/POST /v1/unsubscribe` and `GET /email/{name}`.

`GET /v1/unsubscribe?t=…` only shows a confirmation: link scanners and previews follow
links, and the draft's GET unsubscribed on a mere visit. `POST` applies it — the one-click
POST of a mail client (RFC 8058, `List-Unsubscribe=One-Click`, token in the URL) or the
page's form (token in the body as the draft's `token` field). Both answer the same whether
the token is ours or not: JSON `{"unsubscribed": true}`, or for a browser a 303 to the
done page. No cookie, no session: the token is the only authority.

Both routes are public and limited per client address with the GCRA limiter; images get a
wide limit, since a mail provider's image proxy fetches for many readers from few addresses.
"""

from collections.abc import Mapping
from datetime import timedelta
from http import HTTPStatus
from typing import Annotated, Final
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel
from starlette.requests import Request

from shosai.core.email.images import IMAGE_CACHE, EmailImage
from shosai.core.email.links import UNSUBSCRIBE_PATH
from shosai.core.email.page import PAGE_HEADERS, UnsubscribePage
from shosai.core.email.unsubscribe import Unsubscribes
from shosai.core.kernel.errors import AppError
from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.web.envelope import ERROR_RESPONSES
from shosai.core.web.rate_limit import rate_limited

UNSUBSCRIBE_LIMIT: Final = RateLimit("email_unsubscribe", 30, timedelta(minutes=1), 10)
IMAGE_LIMIT: Final = RateLimit("email_images", 600, timedelta(minutes=1), 200)
MAX_TOKEN: Final = 512
MAX_FORM_BYTES: Final = 4096
FORM_BODY: Final = {
    "requestBody": {
        "required": False,
        "content": {
            "application/x-www-form-urlencoded": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "token": {"type": "string", "maxLength": MAX_TOKEN},
                        "List-Unsubscribe": {"type": "string", "enum": ["One-Click"]},
                    },
                }
            }
        },
    }
}

JSON_ERRORS: Final = {
    "description": ERROR_RESPONSES["default"]["description"],
    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
}

type Token = Annotated[str, Query(alias="t", max_length=MAX_TOKEN)]
type AcceptLanguage = Annotated[str | None, Header(max_length=256)]


class UnsubscribeAnswer(BaseModel):
    """The same answer for every token: nothing about the account behind it."""

    unsubscribed: bool


async def form_token(request: Request) -> str:
    """The `token` field of a small urlencoded body; a larger body carries none."""
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_FORM_BYTES:
            return ""
    fields = parse_qs(body.decode("utf-8", "replace"), max_num_fields=4)
    return next(iter(fields.get("token", [])), "")[:MAX_TOKEN]


def build_email_links_router(
    unsubscribes: Unsubscribes,
    page: UnsubscribePage,
    images: Mapping[str, EmailImage],
    limiter: RateLimiter,
) -> APIRouter:
    """The public routes that mail links to."""
    router = APIRouter(tags=["email"])
    unsubscribe_limit = [Depends(rate_limited(limiter, UNSUBSCRIBE_LIMIT))]

    # Конверт ошибок — JSON, хотя страница HTML: описан явно, иначе OpenAPI взял бы text/html.
    @router.get(
        UNSUBSCRIBE_PATH,
        response_class=HTMLResponse,
        dependencies=unsubscribe_limit,
        responses={"default": JSON_ERRORS},
    )
    async def unsubscribe_page(
        *,
        accept_language: AcceptLanguage = None,
        link_token: Token = "",
        done: Annotated[bool, Query()] = False,
    ) -> HTMLResponse:
        """Ask before unsubscribing; after the form, say it is done."""
        return HTMLResponse(
            page.render(accept_language, link_token, done=done), headers=PAGE_HEADERS
        )

    @router.post(
        UNSUBSCRIBE_PATH,
        dependencies=unsubscribe_limit,
        response_model=UnsubscribeAnswer,
        responses={HTTPStatus.SEE_OTHER: {"description": "A browser goes to the done page."}},
        openapi_extra=FORM_BODY,
    )
    async def unsubscribe(
        body_token: Annotated[str, Depends(form_token)],
        link_token: Token = "",
        accept: Annotated[str, Header(max_length=1024)] = "",
    ) -> Response:
        """Unsubscribe the person the token names from its kind of mail."""
        await unsubscribes.apply(link_token or body_token)
        if "text/html" in accept:
            return RedirectResponse(f"{UNSUBSCRIBE_PATH}?done=true", HTTPStatus.SEE_OTHER)
        return JSONResponse(UnsubscribeAnswer(unsubscribed=True).model_dump())

    @router.get(
        "/email/{name}",
        include_in_schema=False,
        dependencies=[Depends(rate_limited(limiter, IMAGE_LIMIT))],
    )
    async def email_image(
        name: str, if_none_match: Annotated[str | None, Header(max_length=256)] = None
    ) -> Response:
        """An image of the mail layout from the fixed list."""
        image = images.get(name)
        if image is None:
            raise AppError("not_found", HTTPStatus.NOT_FOUND)
        headers = {"Cache-Control": IMAGE_CACHE, "ETag": image.etag}
        if if_none_match == image.etag:
            return Response(status_code=HTTPStatus.NOT_MODIFIED, headers=headers)
        return Response(image.content, media_type="image/png", headers=headers)

    return router

"""Social sign-in routes: `/v1/auth/social/*` (web; the callback and the token page external).

`/callback` and `/yandex/token-page` are the addresses registered with the providers. The
callback answers only redirects to the cabinet's sign-in page, never JSON, whatever
happens; an unexpected failure is logged and shown as `social_failed`.
"""

import base64
import hashlib
from datetime import timedelta
from typing import Annotated, Final

import structlog
from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel
from starlette.responses import HTMLResponse, RedirectResponse

from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.web.rate_limit import rate_limited
from shosai.features.identity.application.social import Outcome, SocialRefusedError, SocialSignIn
from shosai.features.identity.domain.social import Provider, visible_providers
from shosai.features.identity.infrastructure.social.base import SocialProviderFailedError
from shosai.features.identity.infrastructure.social.flows import SocialStateUnavailableError

SOCIAL_LIMIT: Final = RateLimit("identity.social", 20, timedelta(minutes=1), 20)
CALLBACK_LIMIT: Final = RateLimit("identity.social_callback", 30, timedelta(minutes=1), 30)
# Страна посетителя от edge (GeoIP, F4); от клиента страна не принимается (406-ФЗ).
COUNTRY_HEADER: Final = "X-Country-Code"
RELAY_SCRIPT: Final = "window.YaSendSuggestToken(window.location.origin);"
RELAY_SCRIPT_HASH: Final = base64.b64encode(
    hashlib.sha256(RELAY_SCRIPT.encode("utf-8")).digest()
).decode("ascii")
YANDEX_SDK: Final = (
    "https://yastatic.net/s3/passport-sdk/autofill/v1/sdk-suggest-token-with-polyfills-latest.js"
)
TOKEN_PAGE: Final = (
    '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Shosai</title>'
    f'<script src="{YANDEX_SDK}"></script></head>'
    f"<body><script>{RELAY_SCRIPT}</script></body></html>"
)
TOKEN_PAGE_HEADERS: Final = {
    "Content-Security-Policy": (
        f"default-src 'none'; script-src https://yastatic.net 'sha256-{RELAY_SCRIPT_HASH}'; "
        "connect-src https://*.yandex.ru https://*.yandex.net; frame-ancestors 'none'"
    ),
    "Cache-Control": "no-store",
}
log = structlog.stdlib.get_logger(__name__)


class ProvidersAnswer(BaseModel):
    """The providers this visitor sees, and what their widgets need."""

    providers: list[Provider]
    yandex_client_id: str | None
    google_client_id: str | None


def build_social_router(
    social: SocialSignIn, limiter: RateLimiter, widget_ids: dict[Provider, str]
) -> APIRouter:
    """The social sign-in routes."""
    router = APIRouter(prefix="/v1/auth/social", tags=["auth"])
    limited = [Depends(rate_limited(limiter, SOCIAL_LIMIT))]

    @router.get("/providers", dependencies=limited)
    async def providers(
        language: Annotated[str, Query(max_length=16)] = "en",
        country: Annotated[str | None, Header(alias=COUNTRY_HEADER, max_length=2)] = None,
    ) -> ProvidersAnswer:
        """The providers shown to this visitor; never both sets (406-FZ)."""
        shown = [p for p in visible_providers(country, language) if social.enabled(p)]
        return ProvidersAnswer(
            providers=shown,
            yandex_client_id=widget_ids.get(Provider.YANDEX),
            google_client_id=widget_ids.get(Provider.GOOGLE),
        )

    @router.get("/yandex/token-page", include_in_schema=False)
    async def yandex_token_page() -> HTMLResponse:
        """The page Yandex's widget returns to; it hands the token to the opener."""
        return HTMLResponse(TOKEN_PAGE, headers=TOKEN_PAGE_HEADERS)

    @router.get("/{provider}/start", dependencies=limited, include_in_schema=False)
    async def start(
        provider: str,
        next_path: Annotated[str | None, Query(alias="next", max_length=256)] = None,
        language: Annotated[str, Query(max_length=16)] = "en",
        country: Annotated[str | None, Header(alias=COUNTRY_HEADER, max_length=2)] = None,
    ) -> RedirectResponse:
        """Off to the provider, or back to the sign-in page with the reason."""
        chosen = _provider(provider)
        if chosen is None or chosen not in visible_providers(country, language):
            return _redirect(social.redirect(None, "social_provider_disabled", Provider.YANDEX))
        try:
            return _redirect(await social.start(chosen, next_path, language))
        except (SocialRefusedError, SocialStateUnavailableError) as error:
            code = getattr(error, "code", "social_unavailable")
            return _redirect(social.redirect(None, code, chosen))

    @router.get(
        "/{provider}/callback",
        dependencies=[Depends(rate_limited(limiter, CALLBACK_LIMIT))],
        include_in_schema=False,
    )
    async def callback(
        provider: str,
        code: Annotated[str | None, Query(max_length=1024)] = None,
        state: Annotated[str | None, Query(max_length=256)] = None,
        device_id: Annotated[str | None, Query(max_length=256)] = None,
        error: Annotated[str | None, Query(max_length=128)] = None,
    ) -> RedirectResponse:
        """Where the provider sends the person back; always a redirect to the cabinet."""
        chosen = _provider(provider) or Provider.YANDEX
        if error is not None or not code or not state or _provider(provider) is None:
            return _redirect(social.redirect(None, "social_login_cancelled", chosen))
        return _redirect(await _resolved(social, chosen, code, state, device_id))

    return router


async def _resolved(
    social: SocialSignIn, provider: Provider, code: str, state: str, device_id: str | None
) -> str:
    outcome: Outcome | None = None
    try:
        outcome = await social.callback(provider, code, state, device_id)
    except SocialRefusedError as refused:
        return social.redirect(None, refused.code, provider)
    except SocialProviderFailedError:
        log.warning("Провайдер не подтвердил вход", provider=provider.value)
        return social.redirect(None, "social_provider_failed", provider)
    except Exception:
        # Страница входа, а не JSON и не 500: человек видит причину и пробует снова.
        log.exception("Вход через соцсеть сорвался", provider=provider.value)
        return social.redirect(None, "social_failed", provider)
    return social.redirect(outcome, None, provider)


def _provider(value: str) -> Provider | None:
    return Provider(value) if value in Provider else None


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store"})

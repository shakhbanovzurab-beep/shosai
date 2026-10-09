"""The scheme and client address come from `X-Forwarded-*` only through a trusted proxy.

The draft trusted any address (`FORWARDED_ALLOW_IPS="*"`, spec 010). uvicorn applies the
list in front of the app, as `ProxyHeadersMiddleware` does here.
"""

from collections.abc import Sequence
from typing import cast

import httpx
from starlette.types import ASGIApp
from uvicorn._types import ASGI3Application
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from shosai.core.config.sections import WebSettings
from shosai.core.web.app import forwarded_allow_ips
from tests.core.web.probe_app import build_probe_app

EDGE = "10.20.0.7"
FORWARDED_HTTPS = {"X-Forwarded-Proto": "https", "X-Forwarded-For": "203.0.113.9"}


def web_settings(*proxies: str) -> WebSettings:
    """Web settings as `TRUSTED_PROXY_ADDRESSES` would give them."""
    return WebSettings.model_validate({"trusted_proxy_addresses": ",".join(proxies)})


async def hsts_through(peer: str, trusted: Sequence[str]) -> str | None:
    """The HSTS header of a request the peer forwarded as HTTPS."""
    # Один и тот же протокол ASGI описан у uvicorn и у Starlette разными типами.
    proxy = ProxyHeadersMiddleware(
        cast("ASGI3Application", build_probe_app().app), trusted_hosts=list(trusted)
    )
    transport = httpx.ASGITransport(app=cast("ASGIApp", proxy), client=(peer, 40000))
    async with httpx.AsyncClient(transport=transport, base_url="http://api") as client:
        response = await client.get("/v1/health", headers=FORWARDED_HTTPS)
    hsts: str | None = response.headers.get("Strict-Transport-Security")
    return hsts


def test_the_allow_list_is_the_configured_networks() -> None:
    assert forwarded_allow_ips(web_settings("10.20.0.0/16", "192.0.2.1")) == [
        "10.20.0.0/16",
        "192.0.2.1/32",
    ]
    assert forwarded_allow_ips(WebSettings()) == []


async def test_a_trusted_edge_sets_the_scheme() -> None:
    trusted = forwarded_allow_ips(web_settings("10.20.0.0/16"))

    assert await hsts_through(EDGE, trusted) == "max-age=31536000"


async def test_an_untrusted_peer_cannot_claim_https() -> None:
    trusted = forwarded_allow_ips(web_settings("10.30.0.0/16"))

    assert await hsts_through(EDGE, trusted) is None


async def test_without_configured_proxies_nobody_is_trusted() -> None:
    assert await hsts_through("127.0.0.1", forwarded_allow_ips(WebSettings())) is None

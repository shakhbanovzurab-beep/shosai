"""CORS answers only the origins listed in `CORS_ALLOWED_ORIGINS`; by default nobody."""

from shosai.core.config.sections import WebSettings
from shosai.core.web.request_ids import REQUEST_ID_HEADER
from tests.core.web.probe_app import build_probe_app, client_of

ADMIN = "https://admin.shosai.tech"
PREFLIGHT = {"Origin": ADMIN, "Access-Control-Request-Method": "POST"}


def allowing(*origins: str) -> WebSettings:
    """Web settings as `CORS_ALLOWED_ORIGINS` would give them."""
    return WebSettings.model_validate({"cors_allowed_origins": ",".join(origins)})


async def test_a_listed_origin_may_call_with_credentials_and_read_the_request_id() -> None:
    async with client_of(build_probe_app(allowing(ADMIN)).app) as client:
        preflight = await client.options("/v1/health", headers=PREFLIGHT)
        response = await client.get("/v1/health", headers={"Origin": ADMIN})

    assert preflight.status_code == 200
    assert preflight.headers["Access-Control-Allow-Origin"] == ADMIN
    assert preflight.headers["Access-Control-Allow-Credentials"] == "true"
    assert response.headers["Access-Control-Allow-Origin"] == ADMIN
    assert REQUEST_ID_HEADER in response.headers["Access-Control-Expose-Headers"]


async def test_an_unlisted_origin_gets_no_cors_headers() -> None:
    async with client_of(build_probe_app(allowing(ADMIN)).app) as client:
        response = await client.get("/v1/health", headers={"Origin": "https://evil.example"})

    assert "Access-Control-Allow-Origin" not in response.headers


async def test_without_a_list_there_is_no_cors_at_all() -> None:
    async with client_of(build_probe_app().app) as client:
        preflight = await client.options("/v1/health", headers=PREFLIGHT)

    assert preflight.status_code == 405
    assert "Access-Control-Allow-Origin" not in preflight.headers

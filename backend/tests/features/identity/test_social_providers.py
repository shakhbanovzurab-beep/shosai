"""The provider clients against recorded shapes of the providers' answers (step 5)."""

import json
import time
from collections.abc import Callable

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import SecretStr

from shosai.features.identity.infrastructure.social.base import SocialProviderFailedError
from shosai.features.identity.infrastructure.social.github import GitHub
from shosai.features.identity.infrastructure.social.google import Google
from shosai.features.identity.infrastructure.social.vk import Vk
from shosai.features.identity.infrastructure.social.yandex import Yandex

SECRET = SecretStr("client-secret")
REDIRECT = "https://shosai.example/v1/auth/social/x/callback"
PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def http(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_a_yandex_token_issued_to_another_app_is_refused() -> None:
    def answer(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "OAuth widget-token"
        return httpx.Response(200, json={"id": "42", "client_id": "someone-else"})

    with pytest.raises(SocialProviderFailedError):
        await Yandex(http(answer), "ours", SECRET, REDIRECT).identify_token("widget-token")


async def test_a_yandex_token_of_this_app_proves_its_address() -> None:
    def answer(_request: httpx.Request) -> httpx.Response:
        profile = {
            "id": "42",
            "client_id": "ours",
            "default_email": "Anna@Yandex.RU",
            "real_name": "Anna",
        }
        return httpx.Response(200, json=profile)

    found = await Yandex(http(answer), "ours", SECRET, REDIRECT).identify_token("t")

    assert (found.subject, found.email, found.email_verified) == ("42", "anna@yandex.ru", True)


def google_token(audience: str, *, expires_in: int = 600, key_id: str = "k1") -> str:
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com", "aud": audience, "sub": "g-7", "iat": now,
        "exp": now + expires_in, "email": "anna@gmail.com", "email_verified": True,
    }  # fmt: skip
    return jwt.encode(claims, PRIVATE_KEY, algorithm="RS256", headers={"kid": key_id})


def google_keys(_request: httpx.Request) -> httpx.Response:
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(PRIVATE_KEY.public_key()))
    return httpx.Response(200, json={"keys": [{**public, "kid": "k1", "alg": "RS256"}]})


async def test_a_google_id_token_is_checked_against_the_published_keys() -> None:
    google = Google(http(google_keys), "ours", SECRET, REDIRECT)

    found = await google.identify_token(google_token("ours"))

    assert (found.subject, found.email, found.email_verified) == ("g-7", "anna@gmail.com", True)


@pytest.mark.parametrize(
    "token",
    [
        google_token("someone-else"),
        google_token("ours", expires_in=-60),
        google_token("ours", key_id="k9"),
    ],
)
async def test_a_foreign_expired_or_unknown_google_token_is_refused(token: str) -> None:
    with pytest.raises(SocialProviderFailedError):
        await Google(http(google_keys), "ours", SECRET, REDIRECT).identify_token(token)


async def test_github_takes_the_primary_verified_address_and_skips_noreply() -> None:
    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login/oauth/access_token":
            return httpx.Response(200, json={"access_token": "gh"})
        if request.url.path == "/user":
            return httpx.Response(200, json={"id": 99, "login": "anna"})
        return httpx.Response(
            200,
            json=[
                {"email": "anna@users.noreply.github.com", "verified": True, "primary": True},
                {"email": "old@example.com", "verified": False, "primary": False},
                {"email": "Anna@Example.com", "verified": True, "primary": False},
            ],
        )

    found = await GitHub(http(answer), "ours", SECRET, REDIRECT).identify("code", "v" * 43, None)

    assert (found.subject, found.email, found.email_verified) == ("99", "anna@example.com", True)


async def test_vk_needs_its_device_id_and_proves_no_address() -> None:
    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/auth":
            assert b"device_id=dev-1" in request.content
            return httpx.Response(200, json={"access_token": "vk"})
        return httpx.Response(200, json={"user": {"user_id": 5, "email": "a@vk.com"}})

    vk = Vk(http(answer), "ours", REDIRECT)
    found = await vk.identify("code", "v" * 43, "dev-1")

    assert (found.subject, found.email, found.email_verified) == ("5", "a@vk.com", False)
    with pytest.raises(SocialProviderFailedError):
        await vk.identify("code", "v" * 43, None)


def test_every_authorize_url_carries_the_state_and_an_s256_challenge() -> None:
    client = http(lambda _request: httpx.Response(500))
    urls = [
        Yandex(client, "ours", SECRET, REDIRECT).authorize_url("st", "ch"),
        Vk(client, "ours", REDIRECT).authorize_url("st", "ch"),
        Google(client, "ours", SECRET, REDIRECT).authorize_url("st", "ch"),
        GitHub(client, "ours", SECRET, REDIRECT).authorize_url("st", "ch"),
    ]

    for url in urls:
        assert "state=st" in url
        assert "code_challenge=ch" in url
        assert "code_challenge_method=S256" in url

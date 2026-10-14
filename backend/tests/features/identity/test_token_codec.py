"""Tokens stay compatible with the draft and carry the home (ADR 0045 point 1, R6)."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import SecretStr

from shosai.core.kernel.homes import Home
from shosai.features.identity.domain.tokens import (
    ACCESS_TOKEN_LIFETIME,
    AccessClaims,
    InvalidTokenError,
    RefreshClaims,
)
from shosai.features.identity.infrastructure.token_codec import TokenCodec
from shosai.features.identity.settings import TokenKey

NEW_KEY = TokenKey("k1", SecretStr("n" * 48))
DRAFT_SECRET = "draft-jwt-secret-" + "x" * 32
DRAFT_KEY = TokenKey("d", SecretStr(DRAFT_SECRET))


def now() -> int:
    # Время берётся в момент вызова: в полном прогоне тест идёт через минуты после импорта.
    return int(datetime.now(UTC).timestamp())


def at(seconds: int) -> datetime:
    return datetime.fromtimestamp(now() + seconds, UTC)


def access(home: Home | None = Home.RU, version: int = 2) -> AccessClaims:
    return AccessClaims(uuid.uuid4(), home, version, at(0), at(1800))


def draft_token(payload: dict[str, object], secret: str = DRAFT_SECRET) -> str:
    # Так подписывает черновик: HS256, без заголовка kid (core/jwt_utils.py черновика).
    return jwt.encode(payload, secret, algorithm="HS256")


@given(
    st.uuids(),
    st.sampled_from([Home.RU, Home.EU, None]),
    st.integers(min_value=0, max_value=10_000),
    st.integers(min_value=60, max_value=int(ACCESS_TOKEN_LIFETIME.total_seconds())),
)
def test_access_claims_survive_a_round_trip(
    user_id: uuid.UUID, home: Home | None, version: int, lifetime: int
) -> None:
    claims = AccessClaims(user_id, home, version, at(0), at(lifetime))
    codec = TokenCodec((NEW_KEY, DRAFT_KEY))

    assert codec.decode_access(codec.encode_access(claims)) == claims


@given(st.uuids(), st.uuids(), st.text(alphabet="abcdef0123456789", min_size=8, max_size=64))
def test_refresh_claims_survive_a_round_trip(
    user_id: uuid.UUID, family_id: uuid.UUID, token_id: str
) -> None:
    claims = RefreshClaims(user_id, Home.EU, 1, family_id, token_id, at(0), at(600))
    codec = TokenCodec((NEW_KEY,))

    assert codec.decode_refresh(codec.encode_refresh(claims)) == claims


def test_a_draft_access_token_without_kid_or_home_is_accepted() -> None:
    user_id = uuid.uuid4()
    token = draft_token(
        {"sub": str(user_id), "typ": "access", "tv": 3, "iat": now(), "exp": now() + 60}
    )

    claims = TokenCodec((NEW_KEY, DRAFT_KEY)).decode_access(token)

    assert (claims.user_id, claims.home, claims.token_version) == (user_id, None, 3)


def test_a_draft_refresh_token_keeps_its_family_and_id() -> None:
    family = uuid.uuid4()
    payload = {"sub": str(uuid.uuid4()), "typ": "refresh", "tv": 0, "iat": now(), "exp": now() + 60}
    token = draft_token({**payload, "fid": str(family), "jti": "abc123"})

    claims = TokenCodec((NEW_KEY, DRAFT_KEY)).decode_refresh(token)

    assert (claims.family_id, claims.token_id) == (family, "abc123")


def test_a_draft_token_older_than_the_version_counter_has_version_zero() -> None:
    token = draft_token(
        {"sub": str(uuid.uuid4()), "typ": "access", "iat": now(), "exp": now() + 60}
    )

    assert TokenCodec((NEW_KEY, DRAFT_KEY)).decode_access(token).token_version == 0


def test_a_refresh_token_never_opens_a_request_and_an_access_token_never_refreshes() -> None:
    codec = TokenCodec((NEW_KEY,))
    refresh = RefreshClaims(uuid.uuid4(), Home.RU, 0, uuid.uuid4(), "jti", at(0), at(60))

    with pytest.raises(InvalidTokenError, match="wrong_token_kind"):
        codec.decode_access(codec.encode_refresh(refresh))
    with pytest.raises(InvalidTokenError, match="wrong_token_kind"):
        codec.decode_refresh(codec.encode_access(access()))


def test_the_first_key_signs_and_names_itself() -> None:
    token = TokenCodec((NEW_KEY, DRAFT_KEY)).encode_access(access())

    assert jwt.get_unverified_header(token)["kid"] == "k1"


def test_with_the_draft_key_first_the_draft_can_still_read_new_tokens() -> None:
    # Откат на черновик: он проверяет своим секретом и не смотрит на kid.
    token = TokenCodec((DRAFT_KEY, NEW_KEY)).encode_access(access(Home.EU))

    payload = jwt.decode(token, DRAFT_SECRET, algorithms=["HS256"])

    assert (payload["typ"], payload["home"]) == ("access", "eu")


@pytest.mark.parametrize(
    ("token", "reason"),
    [
        ("not-a-token", "malformed_token"),
        (jwt.encode({"typ": "access"}, "n" * 48, "HS256", headers={"kid": "k9"}), "unknown_key"),
        (jwt.encode({"typ": "access"}, "x" * 48, "HS256", headers={"kid": "k1"}), "invalid"),
        (jwt.encode({"typ": "access"}, "n" * 64, "HS512", headers={"kid": "k1"}), "invalid"),
        (
            draft_token({"sub": "x", "typ": "access", "iat": now(), "exp": now() + 60}),
            "unknown_key",
        ),
    ],
)
def test_a_forged_or_foreign_token_is_refused(token: str, reason: str) -> None:
    with pytest.raises(InvalidTokenError, match=reason):
        TokenCodec((NEW_KEY,)).decode_access(token)


def test_an_expired_token_is_refused_as_expired() -> None:
    claims = AccessClaims(uuid.uuid4(), Home.RU, 0, at(-120), at(-60))
    codec = TokenCodec((NEW_KEY,))

    with pytest.raises(InvalidTokenError, match="expired"):
        codec.decode_access(codec.encode_access(claims))


@pytest.mark.parametrize(
    ("claims", "reason"),
    [
        ({"sub": "not-a-uuid", "tv": 0}, "malformed_sub"),
        ({"sub": str(uuid.uuid4()), "tv": -1}, "malformed_tv"),
        ({"sub": str(uuid.uuid4()), "tv": 0, "home": "us"}, "unknown_home"),
    ],
)
def test_a_signed_token_with_broken_claims_is_refused(
    claims: dict[str, object], reason: str
) -> None:
    token = draft_token({**claims, "typ": "access", "iat": now(), "exp": now() + 60})

    with pytest.raises(InvalidTokenError, match=reason):
        TokenCodec((DRAFT_KEY,)).decode_access(token)


def test_a_draft_refresh_token_without_jti_is_refused() -> None:
    token = draft_token(
        {"sub": str(uuid.uuid4()), "typ": "refresh", "iat": now(), "exp": now() + 60}
    )

    with pytest.raises(InvalidTokenError, match="refresh_without_jti"):
        TokenCodec((DRAFT_KEY,)).decode_refresh(token)


def test_an_empty_ring_is_a_configuration_error() -> None:
    with pytest.raises(ValueError, match="пусто"):
        TokenCodec(())


def test_lifetimes_follow_the_native_contract() -> None:
    assert timedelta(minutes=30) == ACCESS_TOKEN_LIFETIME

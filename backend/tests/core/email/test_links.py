"""Unsubscribe tokens: ours and the draft's are read, anything altered or foreign is not."""

import hashlib
import hmac
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import SecretStr

from shosai.core.email.links import UnsubscribeLinks, Unsubscription
from shosai.core.email.messages import EmailKind
from shosai.core.kernel.homes import Home
from tests.core.email.bench import DRAFT_SECRET, LINK_SECRET, USER_ID, mail_links


def token_of(url: str | None) -> str:
    """The `t` of an unsubscribe URL."""
    assert url is not None
    return parse_qs(urlsplit(url).query)["t"][0]


def draft_token(user_id: UUID, secret: SecretStr = DRAFT_SECRET) -> str:
    """A token as the draft built it (`services/email/unsubscribe_link.py`)."""
    raw = str(user_id)
    key = secret.get_secret_value().encode()
    return f"{raw}.{hmac.new(key, raw.encode(), hashlib.sha256).hexdigest()[:32]}"


V2_TOKEN = token_of(mail_links().url(Home.EU, USER_ID, EmailKind.NOTIFICATION))


@pytest.mark.parametrize("home", list(Home))
@pytest.mark.parametrize("kind", [EmailKind.NOTIFICATION, EmailKind.NEWSLETTER])
def test_a_v2_link_names_its_home_person_and_kind(home: Home, kind: EmailKind) -> None:
    links = mail_links()
    url = links.url(home, USER_ID, kind)

    assert url is not None
    assert url.startswith("https://shosai.example/v1/unsubscribe?t=v2.")
    assert links.read(token_of(url)) == Unsubscription(home, USER_ID, kind)


def test_account_mail_has_no_link_and_development_without_the_secret_signs_none() -> None:
    unsigned = UnsubscribeLinks("https://shosai.example", None, None)

    assert mail_links().url(Home.EU, USER_ID, EmailKind.ACCOUNT) is None
    assert unsigned.url(Home.EU, USER_ID, EmailKind.NEWSLETTER) is None
    assert unsigned.read(V2_TOKEN) is None


def test_a_draft_link_suppresses_newsletters_in_the_russian_home() -> None:
    asked = mail_links().read(draft_token(USER_ID))

    assert asked == Unsubscription(Home.RU, USER_ID, EmailKind.NEWSLETTER, from_draft=True)


@pytest.mark.parametrize(
    "token",
    [
        "",
        "v2",
        "v2.eu.notification",
        V2_TOKEN.replace(".eu.", ".ru."),
        V2_TOKEN.replace(".notification.", ".newsletter."),
        V2_TOKEN.replace(USER_ID.hex, UUID(int=1).hex),
        V2_TOKEN + "x",
        token_of(
            UnsubscribeLinks("https://shosai.example", SecretStr("another-secret-" * 3), None).url(
                Home.EU, USER_ID, EmailKind.NOTIFICATION
            )
        ),
        draft_token(USER_ID, SecretStr("not-the-draft-secret")),
        draft_token(USER_ID)[:-1],
        f"{USER_ID}.",
        ".abc",
    ],
)
def test_an_altered_or_foreign_token_is_no_token(token: str) -> None:
    assert mail_links().read(token) is None


def test_the_draft_secret_does_not_sign_v2_links_and_the_link_secret_not_draft_ones() -> None:
    swapped = UnsubscribeLinks("https://shosai.example", DRAFT_SECRET, LINK_SECRET)

    assert swapped.read(V2_TOKEN) is None
    assert swapped.read(draft_token(USER_ID)) is None


def test_a_draft_token_without_the_draft_secret_changes_nothing() -> None:
    links = UnsubscribeLinks("https://shosai.example", LINK_SECRET, None)

    assert links.read(draft_token(USER_ID)) is None


@given(position=st.integers(min_value=0, max_value=len(V2_TOKEN) - 1), char=st.characters())
def test_any_single_changed_character_breaks_a_v2_token(position: int, char: str) -> None:
    altered = V2_TOKEN[:position] + char + V2_TOKEN[position + 1 :]

    assert altered == V2_TOKEN or mail_links().read(altered) is None

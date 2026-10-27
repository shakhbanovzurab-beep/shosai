"""Invitation tokens, principals, session identities and display names (meetings plan §1.2)."""

import uuid

import pytest

from shosai.features.meetings.domain.invites import (
    is_invite_token,
    new_invite_token,
    room_link,
)
from shosai.features.meetings.domain.principals import (
    NAME_MAX,
    NameRuleError,
    Principal,
    PrincipalKind,
    checked_name,
    new_identity,
    principal_of,
)

# Переопределение направления справа налево: им подделывают чужое имя.
RLO = chr(0x202E)


def test_a_new_invite_token_has_12_url_safe_characters_and_old_ones_still_pass() -> None:
    token = new_invite_token()

    assert len(token) == 12
    assert is_invite_token(token)
    assert is_invite_token("A" * 64)
    assert not is_invite_token("A" * 65)
    assert not is_invite_token("short")
    assert not is_invite_token("has space12345")
    assert new_invite_token() != token


def test_the_link_is_the_canonical_meet_path_at_the_origin() -> None:
    assert (
        room_link("https://shosai.tech/", "abcDEF123_-x") == "https://shosai.tech/meet/abcDEF123_-x"
    )


def test_a_principal_is_a_canonical_user_id_or_a_guest() -> None:
    user_id = uuid.uuid4()
    person = Principal.of_user(user_id)
    guest = Principal.new_guest()

    assert (person.kind, person.user_id) == (PrincipalKind.USER, user_id)
    assert (guest.kind, guest.user_id) == (PrincipalKind.GUEST, None)
    assert guest.value.startswith("guest-")
    assert Principal.new_guest() != guest
    for wrong in ("guest-XYZ", str(user_id).upper(), "admin", ""):
        with pytest.raises(ValueError, match="принципал"):
            Principal(wrong)


def test_each_session_has_its_own_identity_and_the_same_principal() -> None:
    principal = Principal.of_user(uuid.uuid4())
    phone, laptop = new_identity(principal), new_identity(principal)

    assert phone != laptop
    assert principal_of(phone) == principal_of(laptop) == principal
    guest = Principal.new_guest()
    assert principal_of(new_identity(guest)) == guest


@pytest.mark.parametrize(
    "identity",
    ["EG_abc123", "agent-1", "guest-0123456789ab", "guest-0123456789ab__xyz", "x__0123abcd"],
)
def test_an_identity_shosai_did_not_mint_has_no_principal(identity: str) -> None:
    assert principal_of(identity) is None


def test_a_display_name_is_trimmed_and_cleaned_of_controls_and_overrides() -> None:
    assert checked_name("  Анна" + RLO + "  ") == "Анна"
    assert checked_name("Ли\x00 Вэй") == "Ли Вэй"
    # ZWJ в эмодзи и ZWNJ в фарси сохраняются.
    assert checked_name("👩‍💻 Dev") == "👩‍💻 Dev"
    assert checked_name("می‌خواهم") == "می‌خواهم"


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (None, "name_required"),
        ("  " + RLO + " ", "name_required"),
        ("я" * (NAME_MAX + 1), "name_too_long"),
    ],
)
def test_a_display_name_breaks_its_rules(raw: str | None, code: str) -> None:
    with pytest.raises(NameRuleError) as error:
        checked_name(raw)
    assert error.value.code == code

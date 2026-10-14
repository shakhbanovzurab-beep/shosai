"""Identity's pure rules: addresses, the directory key, homes, passwords, account states."""

import hmac

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.core.kernel.homes import Home
from shosai.features.identity.domain.accounts import (
    AccountState,
    SignInRefusal,
    sign_in_refusal,
)
from shosai.features.identity.domain.directory import email_hmac
from shosai.features.identity.domain.emails import InvalidEmailError, normalize_email
from shosai.features.identity.domain.homes import (
    CountryCode,
    InvalidCountryError,
    home_for_country,
)
from shosai.features.identity.domain.passwords import (
    PasswordProblem,
    bcrypt_input,
    new_password_problem,
)

KEY = b"k" * 32
local_parts = st.from_regex(r"[A-Za-z0-9._%+-]{1,30}", fullmatch=True)
domains = st.from_regex(r"[A-Za-z0-9-]{1,20}\.[A-Za-z]{2,10}", fullmatch=True)


def test_an_address_is_trimmed_lower_cased_and_its_domain_encoded() -> None:
    assert normalize_email("  Anna.K@Example.COM ").value == "anna.k@example.com"
    assert normalize_email("ivan@пример.рф").value == "ivan@xn--e1afmkfd.xn--p1ai"


@given(local_parts, domains)
def test_normalising_twice_changes_nothing(local: str, domain: str) -> None:
    once = normalize_email(f"{local}@{domain}")

    assert normalize_email(once.value) == once


@given(local_parts, domains)
def test_case_never_separates_two_accounts(local: str, domain: str) -> None:
    lower = normalize_email(f"{local}@{domain}".lower())
    upper = normalize_email(f"{local}@{domain}".upper())

    assert email_hmac(KEY, lower) == email_hmac(KEY, upper)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "a@",
        "@example.com",
        "anna@localhost",
        "an na@example.com",
        "a@b@example.com",
        "a@example..com",
        f"{'a' * 65}@example.com",
        f"a@{'b' * 250}.com",
    ],
)
def test_an_address_identity_cannot_store_is_refused(raw: str) -> None:
    with pytest.raises(InvalidEmailError):
        normalize_email(raw)


def test_the_directory_key_is_hmac_sha256_of_the_normalised_address() -> None:
    email = normalize_email("Anna@Example.com")

    assert email_hmac(KEY, email) == hmac.digest(KEY, b"anna@example.com", "sha256")
    assert email_hmac(b"x" * 32, email) != email_hmac(KEY, email)


def test_russia_lives_in_the_russian_home_every_other_country_in_the_eu() -> None:
    assert home_for_country(CountryCode("RU")) is Home.RU
    assert home_for_country(CountryCode("DE")) is Home.EU
    assert home_for_country(CountryCode("KZ")) is Home.EU


@pytest.mark.parametrize("value", ["ru", "RUS", "R", "1A", ""])
def test_a_country_is_an_iso_alpha_2_code(value: str) -> None:
    with pytest.raises(InvalidCountryError):
        CountryCode(value)


def test_a_new_password_is_8_to_256_characters() -> None:
    assert new_password_problem("1234567") is PasswordProblem.TOO_SHORT
    assert new_password_problem("x" * 257) is PasswordProblem.TOO_LONG
    assert new_password_problem("12345678") is None
    assert new_password_problem("x" * 256) is None


@given(st.text(max_size=300))
def test_bcrypt_reads_the_first_72_bytes_of_the_utf8_encoding(password: str) -> None:
    hashed_input = bcrypt_input(password)

    assert hashed_input == password.encode("utf-8")[:72]
    assert len(hashed_input) <= 72


def test_only_an_active_or_scheduled_account_opens_after_a_correct_password() -> None:
    refusals = {state: sign_in_refusal(state) for state in AccountState}

    assert refusals == {
        AccountState.ACTIVE: None,
        AccountState.DELETION_SCHEDULED: None,
        AccountState.FROZEN: SignInRefusal.FROZEN,
        AccountState.BANNED: SignInRefusal.BANNED,
        AccountState.DELETING: SignInRefusal.DISABLED,
        AccountState.TRANSFERRING: SignInRefusal.DISABLED,
        AccountState.DELETED: SignInRefusal.DISABLED,
    }
    assert {refusal.value for refusal in SignInRefusal} == {
        "account_banned",
        "account_frozen",
        "account_disabled",
    }

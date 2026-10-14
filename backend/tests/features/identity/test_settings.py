"""Identity's settings: the signing ring, the directory key and the gate (ADR 0045)."""

import pytest

from shosai.core.config.gate import UnsafeConfigurationError, enforce_production_gate
from shosai.core.config.loading import ConfigurationError, load_settings
from shosai.features.identity.settings import IdentitySettings, identity_secrets_safe
from tests.core.config.sample_environ import local_environ, production_environ

LONG = "s" * 40
IDENTITY = {
    "IDENTITY_TOKEN_KEYS": f"k2:{LONG}, d:{'d' * 40}",
    "IDENTITY_DIRECTORY_HMAC_KEY": "h" * 40,
}


def test_the_ring_keeps_its_order_and_the_first_key_signs() -> None:
    settings = load_settings(local_environ(**IDENTITY), [IdentitySettings])
    keys = settings.features.get(IdentitySettings).token_keys()

    assert [key.key_id for key in keys] == ["k2", "d"]
    assert keys[0].secret.get_secret_value() == LONG
    assert settings.features.get(IdentitySettings).identity_password_hash_rounds == 12


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("IDENTITY_TOKEN_KEYS", ""),
        ("IDENTITY_TOKEN_KEYS", f"K1:{LONG}"),
        ("IDENTITY_TOKEN_KEYS", f"k1{LONG}"),
        ("IDENTITY_TOKEN_KEYS", f"k1:{LONG},k1:{LONG}"),
        ("IDENTITY_TOKEN_KEYS", "k1:short"),
        ("IDENTITY_DIRECTORY_HMAC_KEY", "short"),
        ("IDENTITY_PASSWORD_HASH_ROUNDS", "3"),
    ],
)
def test_a_broken_value_is_refused_by_name_without_its_value(variable: str, value: str) -> None:
    environ = local_environ(**{**IDENTITY, variable: value})

    with pytest.raises(ConfigurationError) as raised:
        load_settings(environ, [IdentitySettings])

    assert variable in str(raised.value)
    assert LONG not in str(raised.value)


def test_a_missing_section_variable_stops_the_load() -> None:
    environ = local_environ()
    del environ["IDENTITY_TOKEN_KEYS"]

    with pytest.raises(ConfigurationError, match="IDENTITY_TOKEN_KEYS"):
        load_settings(environ, [IdentitySettings])


def test_production_refuses_development_keys_and_cheap_hashing() -> None:
    environ = production_environ(
        IDENTITY_TOKEN_KEYS=f"dev:{LONG}",
        IDENTITY_DIRECTORY_HMAC_KEY="dev-" + "h" * 40,
        IDENTITY_PASSWORD_HASH_ROUNDS="10",
    )

    with pytest.raises(UnsafeConfigurationError) as raised:
        enforce_production_gate(load_settings(environ, [IdentitySettings]), [identity_secrets_safe])

    assert {violation.setting for violation in raised.value.violations} == {
        "IDENTITY_TOKEN_KEYS",
        "IDENTITY_DIRECTORY_HMAC_KEY",
        "IDENTITY_PASSWORD_HASH_ROUNDS",
    }


def test_production_accepts_real_keys() -> None:
    settings = load_settings(production_environ(**IDENTITY), [IdentitySettings])

    enforce_production_gate(settings, [identity_secrets_safe])


def test_a_section_no_slice_declared_is_a_composition_error() -> None:
    settings = load_settings(local_environ())

    with pytest.raises(LookupError, match="IdentitySettings"):
        settings.features.get(IdentitySettings)

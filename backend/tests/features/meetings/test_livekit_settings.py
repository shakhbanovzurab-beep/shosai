"""`LIVEKIT_*`: set as a whole, TLS for clients and a long secret outside development (A2)."""

from collections.abc import Mapping

import pytest

from shosai.composition.features import FEATURES, feature_settings_sections
from shosai.core.config.loading import load_settings
from shosai.features.meetings.settings import LiveKitSettings, livekit_settings_safe
from tests.core.config.sample_environ import production_environ

SECRET = "s" * 32
COMPLETE = {
    "LIVEKIT_URL": "wss://rtc.shosai.tech",
    "LIVEKIT_API_URL": "http://livekit:7880",
    "LIVEKIT_API_KEY": "APIshosai",
    "LIVEKIT_API_SECRET": SECRET,
}


def violations(livekit: Mapping[str, str]) -> dict[str, str]:
    settings = load_settings(
        {**production_environ(), **livekit}, feature_settings_sections(FEATURES)
    )
    return {item.setting: item.reason for item in livekit_settings_safe(settings)}


def test_livekit_set_as_a_whole_over_tls_passes_and_so_does_none() -> None:
    assert violations(COMPLETE) == {}
    assert violations({}) == {}


def test_a_part_of_livekit_names_every_missing_setting() -> None:
    assert set(violations({"LIVEKIT_API_KEY": "APIshosai", "LIVEKIT_API_SECRET": SECRET})) == {
        "LIVEKIT_URL",
        "LIVEKIT_API_URL",
    }


@pytest.mark.parametrize(
    ("change", "setting"),
    [
        ({"LIVEKIT_URL": "ws://rtc.shosai.tech"}, "LIVEKIT_URL"),
        ({"LIVEKIT_API_SECRET": "short-secret"}, "LIVEKIT_API_SECRET"),
    ],
)
def test_a_plain_signal_address_or_a_short_secret_is_refused(
    change: dict[str, str], setting: str
) -> None:
    assert set(violations({**COMPLETE, **change})) == {setting}


def test_the_settings_know_when_they_are_complete() -> None:
    assert LiveKitSettings.model_validate(
        {name.lower(): value for name, value in COMPLETE.items()}
    ).configured
    assert not LiveKitSettings.model_validate({"livekit_api_key": "APIshosai"}).configured

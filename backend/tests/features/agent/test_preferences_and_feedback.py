"""Settings > Leo, and a rated turn kept as an evaluation case (ADR 0068 AG-D4, AG-D13)."""

import dataclasses
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.core.i18n.locales import SUPPORTED_LANGUAGES
from shosai.features.agent.domain.feedback import (
    NAME_MASK,
    case_allowed,
    case_expired,
    mask_names,
)
from shosai.features.agent.domain.preferences import (
    PreferenceRule,
    PreferenceRuleError,
    Preferences,
    Switch,
    answer_language,
    check_preferences,
    native_switches,
)

NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)


def test_everything_is_on_by_default_and_reaches_the_native_me() -> None:
    defaults = Preferences()

    assert all(defaults.switched_on(switch) for switch in Switch)
    assert native_switches(dataclasses.replace(defaults, web_search=False)) == {
        "leo_voice_enabled": True,
        "leo_kb_search_enabled": True,
        "leo_web_search_enabled": False,
        "leo_connector_search_enabled": True,
    }


def test_a_switched_off_or_unknown_switch_keeps_its_tools_away() -> None:
    prefs = Preferences(knowledge_base_search=False)

    assert not prefs.switched_on(Switch.KNOWLEDGE_BASE_SEARCH)
    assert not prefs.switched_on("agent.unknown")
    assert prefs.switched_on(None)


def test_a_model_must_be_auto_or_the_plan_s_and_a_language_one_of_the_sixteen() -> None:
    assert check_preferences(Preferences(), set()) == Preferences()
    assert check_preferences(Preferences(leo_model="m"), {"m"}).leo_model == "m"
    cases: tuple[tuple[Preferences, set[str], PreferenceRule], ...] = (
        (Preferences(leo_model="m"), set(), PreferenceRule.MODEL_UNAVAILABLE),
        (Preferences(response_language="xx"), set(), PreferenceRule.LANGUAGE_INVALID),
    )
    for prefs, models, rule in cases:
        with pytest.raises(PreferenceRuleError) as raised:
            check_preferences(prefs, models)
        assert raised.value.rule is rule


@given(st.sampled_from(["auto", *SUPPORTED_LANGUAGES]), st.none() | st.text(max_size=8))
def test_the_answer_language_is_always_one_of_the_sixteen(
    setting: str, interface: str | None
) -> None:
    language = answer_language(Preferences(response_language=setting), interface)

    assert language in SUPPORTED_LANGUAGES
    if setting != "auto":
        assert language == setting


@given(consent=st.booleans(), spaces=st.lists(st.none() | st.uuids(), max_size=6))
def test_a_case_needs_consent_and_no_workspace_source(
    *, consent: bool, spaces: list[uuid.UUID | None]
) -> None:
    allowed = case_allowed(spaces, consent_given=consent)

    assert allowed == (consent and all(space is None for space in spaces))


def test_the_person_s_names_are_masked_whatever_their_case() -> None:
    text = "Anna Petrova asked; ANNA agreed. Ann stays."

    assert mask_names(text, ["Anna Petrova", "Anna", "A"]) == (
        f"{NAME_MASK} asked; {NAME_MASK} agreed. Ann stays."
    )


def test_a_case_is_kept_a_year_at_most() -> None:
    assert not case_expired(NOW, NOW + timedelta(days=364))
    assert case_expired(NOW, NOW + timedelta(days=365))

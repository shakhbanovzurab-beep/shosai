"""The platform layer, its checks and its versions (ST-D1, ADR 0074)."""

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from types import MappingProxyType
from typing import TypedDict, Unpack
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.core.kernel.latin_script import non_latin_letters
from shosai.features.studio.domain.errors import StudioRule, StudioRuleError
from shosai.features.studio.domain.platform_layer import (
    BUILT_IN,
    LAYER_TOKENS,
    RULES_HEADING,
    FeaturePrompt,
    PlatformConfig,
    PlatformFeature,
    SafetyRule,
    check_publishable,
    cleaned,
    feature_text,
    layer_text,
)
from shosai.features.studio.domain.versions import (
    Version,
    next_number,
    publication,
    restoration,
)


class ConfigChanges(TypedDict, total=False):
    """The fields of a config a test may set."""

    system_prompt: str
    rules: tuple[SafetyRule, ...]
    blocked_topics: tuple[str, ...]
    features: Mapping[PlatformFeature, FeaturePrompt]


def config(**changes: Unpack[ConfigChanges]) -> PlatformConfig:
    """A config with a system prompt, two rules — one empty — and a topic."""
    base = PlatformConfig(
        system_prompt="  Answer plainly.  ",
        rules=(
            SafetyRule("r1", " Cite sources. ", enabled=True),
            SafetyRule("r2", "  ", enabled=True),
        ),
        blocked_topics=("Elections", "elections", " "),
        features=MappingProxyType(
            {
                PlatformFeature.MEETING_SUMMARY: FeaturePrompt(
                    "Lead with decisions.", enabled=True
                ),
                PlatformFeature.VOICE_MODE: FeaturePrompt("Short sentences.", enabled=False),
            }
        ),
    )
    return replace(base, **changes)


def version(number: int, settings: PlatformConfig) -> Version:
    """A published version."""
    return Version(uuid4(), number, cleaned(settings), "", datetime(2026, 10, 27, tzinfo=UTC))


def test_a_published_config_is_trimmed_without_empty_rules_and_with_each_topic_once() -> None:
    clean = cleaned(config())

    assert clean.system_prompt == "Answer plainly."
    assert clean.rules == (SafetyRule("r1", "Cite sources.", enabled=True),)
    assert clean.blocked_topics == ("Elections",)


def test_the_layer_reads_the_prompt_the_enabled_rules_and_the_topics() -> None:
    clean = cleaned(config())

    assert layer_text(clean) == (
        f"Answer plainly.\n\n{RULES_HEADING}\n- Cite sources.\n\n"
        "Decline politely to discuss the following topics, and do not search the web for them: "
        "Elections."
    )
    assert layer_text(BUILT_IN) == ""
    assert feature_text(clean, PlatformFeature.MEETING_SUMMARY) == "Lead with decisions."
    assert feature_text(clean, PlatformFeature.VOICE_MODE) == ""


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"system_prompt": "Отвечай кратко."}, "system_prompt"),
        ({"rules": (SafetyRule("r", "Αλήθεια", enabled=True),)}, "safety.rules.0"),
        ({"blocked_topics": ("政治",)}, "safety.blocked_topics.0"),
        (
            {
                "features": MappingProxyType(
                    {PlatformFeature.VOICE_MODE: FeaturePrompt("Говори коротко", enabled=True)}
                )
            },
            "features.voice_mode",
        ),
    ],
)
def test_text_a_model_would_read_must_be_english(changes: ConfigChanges, field: str) -> None:
    with pytest.raises(StudioRuleError) as raised:
        check_publishable(cleaned(config(**changes)))

    assert raised.value.rule is StudioRule.PLATFORM_PROMPT_NOT_ENGLISH
    assert raised.value.params == {"field": field}


def test_a_disabled_rule_is_not_read_so_it_is_not_checked() -> None:
    check_publishable(cleaned(config(rules=(SafetyRule("r", "Правило", enabled=False),))))


@given(st.text(max_size=60))
def test_the_publish_check_refuses_exactly_what_the_model_facing_test_refuses(text: str) -> None:
    candidate = cleaned(config(system_prompt=text, rules=(), blocked_topics=()))
    if non_latin_letters(candidate.system_prompt):
        with pytest.raises(StudioRuleError):
            check_publishable(candidate)
    else:
        check_publishable(candidate)


def test_a_layer_over_its_budget_is_refused_with_its_size() -> None:
    with pytest.raises(StudioRuleError) as raised:
        check_publishable(cleaned(config(system_prompt="word " * 700)))

    assert raised.value.rule is StudioRule.PLATFORM_LAYER_OVER_BUDGET
    assert raised.value.params["max"] == LAYER_TOKENS


def test_a_publish_numbers_the_version_and_refuses_what_is_already_live() -> None:
    draft = config()

    first = publication(draft, None, " First. ")
    live = version(first.number, draft)

    assert (first.number, first.comment, first.config) == (1, "First.", cleaned(draft))
    assert next_number(7) == 8
    for unchanged, current in ((BUILT_IN, None), (draft, live)):
        with pytest.raises(StudioRuleError) as raised:
            publication(unchanged, current, "Again.")
        assert raised.value.rule is StudioRule.NOTHING_TO_PUBLISH


def test_a_restore_publishes_a_copy_checked_by_todays_rules() -> None:
    old = version(1, config())
    live = version(2, config(system_prompt="Answer in detail."))

    copy = restoration(old, live, "")

    assert (copy.number, copy.restored_from, copy.config, copy.comment) == (3, 1, old.config, "")
    with pytest.raises(StudioRuleError) as same:
        restoration(live, live, "")
    assert same.value.rule is StudioRule.NOTHING_TO_PUBLISH
    with pytest.raises(StudioRuleError):
        restoration(version(1, config(system_prompt="Старый слой")), live, "")

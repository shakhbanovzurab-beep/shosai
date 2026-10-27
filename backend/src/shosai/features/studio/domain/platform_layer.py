"""The platform layer the operator publishes, and its checks (ST-D1, ADR 0074).

The layer is the operator's system prompt, then the enabled safety rules in order, then the
blocked topics: English text placed after the code's own policy core in front of Leo and
the desktop answers. A feature prompt is added to its feature's own prompt while enabled.
At publish empty rules are dropped, topics kept once, and what a model would read is checked:
Latin script only (the model-facing test's rule) and within the budget — 1 000 tokens for
the layer, 500 for each feature's addendum. There are no placeholders: the profile core and
the volatile part of Leo's context carry the person's name, zone, time and language.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from shosai.core.kernel.latin_script import non_latin_letters
from shosai.features.studio.domain.errors import StudioRule, StudioRuleError
from shosai.features.studio.domain.prompts import estimate_tokens

SCHEMA: Final = 1
SYSTEM_PROMPT_MAX: Final = 20_000
RULE_MAX: Final = 500
RULES_LIMIT: Final = 50
RULE_ID_MAX: Final = 64
TOPIC_MAX: Final = 80
TOPICS_LIMIT: Final = 100
FEATURE_PROMPT_MAX: Final = 8_000
LAYER_TOKENS: Final = 1_000
FEATURE_TOKENS: Final = 500
# Рамка слоя, которую читает модель: английская, зарегистрирована в тесте model-facing.
RULES_HEADING: Final = "Platform rules, in order:"
TOPICS_LINE: Final = (
    "Decline politely to discuss the following topics, and do not search the web for them: "
    "{topics}."
)
PLATFORM_TEXTS: Final = (RULES_HEADING, TOPICS_LINE)


class PlatformFeature(StrEnum):
    """A feature with its own model call that takes the operator's addendum."""

    MEETING_SUMMARY = "meeting_summary"
    VOICE_MODE = "voice_mode"


@dataclass(frozen=True, slots=True)
class SafetyRule:
    """One rule of the layer; a disabled rule is kept and not sent."""

    id: str
    text: str
    enabled: bool


@dataclass(frozen=True, slots=True)
class FeaturePrompt:
    """The operator's addendum to a feature's prompt."""

    content: str
    enabled: bool


@dataclass(frozen=True, slots=True)
class PlatformConfig:
    """Everything the operator edits on the Platform prompts screen."""

    system_prompt: str
    rules: tuple[SafetyRule, ...]
    blocked_topics: tuple[str, ...]
    features: Mapping[PlatformFeature, FeaturePrompt]


BUILT_IN: Final = PlatformConfig(
    system_prompt="",
    rules=(),
    blocked_topics=(),
    features=MappingProxyType(
        {feature: FeaturePrompt("", enabled=False) for feature in PlatformFeature}
    ),
)


def cleaned(config: PlatformConfig) -> PlatformConfig:
    """The config as it is published: texts trimmed, empty rules dropped, each topic once."""
    rules = tuple(
        replace(rule, text=rule.text.strip()) for rule in config.rules if rule.text.strip()
    )
    topics: dict[str, str] = {}
    for topic in config.blocked_topics:
        text = topic.strip()
        if text:
            topics.setdefault(text.casefold(), text)
    features = {
        feature: FeaturePrompt(prompt.content.strip(), enabled=prompt.enabled)
        for feature, prompt in config.features.items()
    }
    return PlatformConfig(
        config.system_prompt.strip(), rules, tuple(topics.values()), MappingProxyType(features)
    )


def layer_text(config: PlatformConfig) -> str:
    """What a model reads after the policy core; empty while nothing is published."""
    parts = [config.system_prompt] if config.system_prompt else []
    rules = [rule.text for rule in config.rules if rule.enabled]
    if rules:
        parts.append("\n".join([RULES_HEADING, *(f"- {text}" for text in rules)]))
    if config.blocked_topics:
        parts.append(TOPICS_LINE.format(topics="; ".join(config.blocked_topics)))
    return "\n\n".join(parts)


def feature_text(config: PlatformConfig, feature: PlatformFeature) -> str:
    """The addendum a feature's call takes; empty when it is off."""
    prompt = config.features.get(feature)
    return prompt.content if prompt is not None and prompt.enabled else ""


def sent_texts(config: PlatformConfig) -> tuple[tuple[str, str], ...]:
    """Every text of the config a model reads, with the field it comes from."""
    texts = [("system_prompt", config.system_prompt)]
    texts.extend(
        (f"safety.rules.{index}", rule.text)
        for index, rule in enumerate(config.rules)
        if rule.enabled
    )
    texts.extend(
        (f"safety.blocked_topics.{index}", topic)
        for index, topic in enumerate(config.blocked_topics)
    )
    texts.extend(
        (f"features.{feature.value}", feature_text(config, feature)) for feature in PlatformFeature
    )
    return tuple(texts)


def check_publishable(config: PlatformConfig) -> None:
    """Refuse a cleaned config a model must not read: non-English text or over budget."""
    for field, text in sent_texts(config):
        if non_latin_letters(text):
            raise StudioRuleError(StudioRule.PLATFORM_PROMPT_NOT_ENGLISH, {"field": field})
    tokens = estimate_tokens(layer_text(config))
    if tokens > LAYER_TOKENS:
        raise StudioRuleError(
            StudioRule.PLATFORM_LAYER_OVER_BUDGET,
            {"field": "layer", "tokens": tokens, "max": LAYER_TOKENS},
        )
    for feature in PlatformFeature:
        tokens = estimate_tokens(feature_text(config, feature))
        if tokens > FEATURE_TOKENS:
            raise StudioRuleError(
                StudioRule.PLATFORM_LAYER_OVER_BUDGET,
                {"field": f"features.{feature.value}", "tokens": tokens, "max": FEATURE_TOKENS},
            )

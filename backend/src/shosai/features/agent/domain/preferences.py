"""Settings > Leo: the person's model, answer language, answer length and switches.

Everything is on by default, as in the draft, and a missing row means the defaults. `auto`
lets Leo pick the model; a named model must be one the person's plan offers — none until
studio publishes its catalogue (ADR 0068 AG-D4). `auto` answers in the interface language;
a named language is one of the 16. Anything switched off is neither offered to the model nor
used. The shipped desktop clients read four of the switches from `/v1/auth/me` under the
draft's names.
"""

from collections.abc import Collection, Mapping
from dataclasses import dataclass, fields
from enum import StrEnum
from typing import Final

from shosai.core.i18n.locales import SUPPORTED_LANGUAGES

AUTO: Final = "auto"
DEFAULT_LANGUAGE: Final = "en"


class ResponseLength(StrEnum):
    """How much Leo says by default."""

    CONCISE = "concise"
    BALANCED = "balanced"
    DETAILED = "detailed"


class Switch(StrEnum):
    """A capability the person may switch off; the value is the `ToolSpec.switch` name."""

    WEB_SEARCH = "agent.web_search"
    VOICE_MODE = "agent.voice_mode"
    KNOWLEDGE_BASE_SEARCH = "agent.knowledge_base_search"
    CONNECTED_SERVICES_SEARCH = "agent.connected_services_search"


class PreferenceRule(StrEnum):
    """A rule of the settings; the value is the API's error code."""

    MODEL_UNAVAILABLE = "leo_model_unavailable"
    LANGUAGE_INVALID = "response_language_invalid"


class PreferenceRuleError(ValueError):
    """A setting breaks one of the rules; `rule` is the API's code."""

    def __init__(self, rule: PreferenceRule) -> None:
        super().__init__(rule.value)
        self.rule = rule


@dataclass(frozen=True, slots=True)
class Preferences:
    """Settings > Leo as stored; the defaults are a person who never opened it."""

    leo_model: str = AUTO
    response_language: str = AUTO
    response_length: ResponseLength = ResponseLength.BALANCED
    web_search: bool = True
    voice_mode: bool = True
    knowledge_base_search: bool = True
    connected_services_search: bool = True

    def switched_on(self, switch: str | None) -> bool:
        """Whether a tool behind the switch may be offered; an unknown switch is off."""
        if switch is None:
            return True
        attribute = _SWITCH_FIELDS.get(switch)
        return attribute is not None and bool(getattr(self, attribute))


_SWITCH_FIELDS: Final[Mapping[str, str]] = {
    Switch.WEB_SEARCH: "web_search",
    Switch.VOICE_MODE: "voice_mode",
    Switch.KNOWLEDGE_BASE_SEARCH: "knowledge_base_search",
    Switch.CONNECTED_SERVICES_SEARCH: "connected_services_search",
}
PREFERENCE_FIELDS: Final = tuple(field.name for field in fields(Preferences))


def check_preferences(preferences: Preferences, models: Collection[str]) -> Preferences:
    """The settings if they hold: a model of the plan or `auto`, a platform language or `auto`."""
    if preferences.leo_model != AUTO and preferences.leo_model not in models:
        raise PreferenceRuleError(PreferenceRule.MODEL_UNAVAILABLE)
    language = preferences.response_language
    if language != AUTO and language not in SUPPORTED_LANGUAGES:
        raise PreferenceRuleError(PreferenceRule.LANGUAGE_INVALID)
    return preferences


def answer_language(preferences: Preferences, interface_language: str | None) -> str:
    """The language Leo answers in: the setting, else the interface's, else English."""
    if preferences.response_language != AUTO:
        return preferences.response_language
    if interface_language is not None and interface_language in SUPPORTED_LANGUAGES:
        return interface_language
    return DEFAULT_LANGUAGE


def native_switches(preferences: Preferences) -> dict[str, bool]:
    """The four switches of the native `/v1/auth/me`, by the draft's names."""
    return {
        "leo_voice_enabled": preferences.voice_mode,
        "leo_kb_search_enabled": preferences.knowledge_base_search,
        "leo_web_search_enabled": preferences.web_search,
        "leo_connector_search_enabled": preferences.connected_services_search,
    }

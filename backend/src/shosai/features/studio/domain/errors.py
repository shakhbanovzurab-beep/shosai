"""The rules studio refuses by, each the code of the platform's error envelope (ADR 0008).

The cabinet words every code in the person's language (Studio) or in Russian (the admin
panel); the parameters are what its wording needs, never a person's text.
"""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

from shosai.core.kernel.errors import ErrorParam


class StudioRule(StrEnum):
    """A rule a write broke; the value is the API's error code."""

    CONTEXT_TOO_LONG = "context_too_long"
    PROMPT_NAME_REQUIRED = "prompt_name_required"
    PROMPT_NAME_TOO_LONG = "prompt_name_too_long"
    PROMPT_TOO_LONG = "prompt_too_long"
    PROMPT_OVER_BUDGET = "prompt_over_budget"
    TOO_MANY_SKILLS = "too_many_skills"
    SKILL_NOT_INSTALLED = "skill_not_installed"
    PROMPT_LIMIT_REACHED = "prompt_limit_reached"
    PROMPT_NOT_FOUND = "prompt_not_found"
    PROMPT_FOR_OTHER_ROLE = "prompt_for_other_role"
    MODEL_NOT_ON_PLAN = "model_not_on_plan"
    MODEL_CANT_DO_ROLE = "model_cant_do_role"
    MAX_TOKENS_RANGE = "max_tokens_range"
    MODEL_NOT_FOUND = "model_not_found"
    MODEL_NOT_ON_OPENROUTER = "model_not_on_openrouter"
    MODEL_ALREADY_LISTED = "model_already_listed"
    MODEL_IS_DEFAULT = "model_is_default"
    MODEL_DISABLED = "model_disabled"
    MODEL_ENABLED = "model_enabled"
    DEFAULT_NOT_STANDARD = "default_not_standard"
    FALLBACK_SAME_AS_DEFAULT = "fallback_same_as_default"
    NO_TIER_PROPOSAL = "no_tier_proposal"
    OPENROUTER_UNREACHABLE = "openrouter_unreachable"
    PLATFORM_PROMPT_NOT_ENGLISH = "platform_prompt_not_english"
    PLATFORM_LAYER_OVER_BUDGET = "platform_layer_over_budget"
    NOTHING_TO_PUBLISH = "nothing_to_publish"
    VERSION_NOT_FOUND = "version_not_found"


class StudioRuleError(ValueError):
    """A write that breaks a rule of studio; the channel turns it into an error answer."""

    def __init__(self, rule: StudioRule, params: Mapping[str, ErrorParam] | None = None) -> None:
        super().__init__(rule.value)
        self.rule = rule
        self.params: Mapping[str, ErrorParam] = MappingProxyType(dict(params or {}))

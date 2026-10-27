"""A person's prompts, skills, context and model settings (studio plan §2, ADR 0074)."""

from dataclasses import replace
from decimal import Decimal
from typing import TypedDict, Unpack
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.studio.domain.errors import StudioRule, StudioRuleError
from shosai.features.studio.domain.model_settings import call_settings, checked_settings
from shosai.features.studio.domain.prompts import (
    CONTEXT_MAX,
    NAME_MAX,
    ROLE_PROMPT_TOKENS,
    SKILLS_MAX,
    PromptDraft,
    SkillText,
    check_budget,
    checked_context,
    checked_draft,
    fitting_skills,
    prompt_tokens,
)
from shosai.features.studio.domain.roles import (
    TEXT_AND_VISION,
    PromptRole,
    RoleSettings,
    Tier,
    default_settings,
)
from tests.features.studio.catalogue_kit import model


class DraftChanges(TypedDict, total=False):
    """The fields of a draft a test may set."""

    name: str
    content: str
    skill_ids: tuple[UUID, ...]


def draft(**changes: Unpack[DraftChanges]) -> PromptDraft:
    """A prompt as the editor sends it."""
    base = PromptDraft(" Interview ", PromptRole.CODE, " Explain the complexity. ", ())
    return replace(base, **changes)


def skill(size: int) -> SkillText:
    """A skill whose body is `size` bytes."""
    return SkillText(uuid4(), "skill", "a" * size)


def test_a_draft_is_trimmed_and_keeps_each_skill_once_in_order() -> None:
    first, second = uuid4(), uuid4()

    stored = checked_draft(draft(skill_ids=(first, second, first)))

    assert (stored.name, stored.content, stored.skill_ids) == (
        "Interview",
        "Explain the complexity.",
        (first, second),
    )


@pytest.mark.parametrize(
    ("changes", "rule"),
    [
        ({"name": "  "}, StudioRule.PROMPT_NAME_REQUIRED),
        ({"name": "n" * (NAME_MAX + 1)}, StudioRule.PROMPT_NAME_TOO_LONG),
        ({"content": "c" * 20_001}, StudioRule.PROMPT_TOO_LONG),
        ({"skill_ids": tuple(uuid4() for _ in range(SKILLS_MAX + 1))}, StudioRule.TOO_MANY_SKILLS),
    ],
)
def test_a_draft_that_breaks_a_limit_is_refused(changes: DraftChanges, rule: StudioRule) -> None:
    with pytest.raises(StudioRuleError) as raised:
        checked_draft(draft(**changes))

    assert raised.value.rule is rule


@given(sizes=st.lists(st.integers(min_value=0, max_value=20_000), max_size=8))
def test_the_skills_that_fit_are_the_first_ones_and_never_exceed_the_budget(
    sizes: list[int],
) -> None:
    skills = [skill(size) for size in sizes]

    kept, left = fitting_skills("instructions", skills)

    assert list(kept) == skills[: len(kept)]
    assert list(left) == [item.skill_id for item in skills[len(kept) :]]
    assert prompt_tokens("instructions", kept) <= ROLE_PROMPT_TOKENS


def test_a_prompt_over_its_budget_is_refused_with_its_size() -> None:
    with pytest.raises(StudioRuleError) as raised:
        check_budget("", [skill(40_000)])

    assert raised.value.rule is StudioRule.PROMPT_OVER_BUDGET
    assert raised.value.params["max"] == ROLE_PROMPT_TOKENS


def test_the_context_is_trimmed_and_counted_in_characters() -> None:
    cyrillic = "я" * CONTEXT_MAX

    assert checked_context(f"  {cyrillic}\n") == cyrillic
    with pytest.raises(StudioRuleError) as raised:
        checked_context(cyrillic + "я")
    assert raised.value.params == {"max": CONTEXT_MAX}


class SettingsChanges(TypedDict, total=False):
    """The fields of model settings a test may set."""

    model_id: str | None
    temperature: Decimal
    max_tokens: int


def settings(**changes: Unpack[SettingsChanges]) -> RoleSettings:
    """Model settings as the cabinet saves them."""
    base = RoleSettings("m", Decimal("0.7"), 4_096, reasoning=True)
    return replace(base, **changes)


def test_saved_settings_need_a_model_the_plan_offers_that_serves_the_role() -> None:
    blind, dear = model("m"), model("m", tier=Tier.FRONTIER, capabilities=TEXT_AND_VISION)
    role = PromptRole.SCREENSHOTS
    cases = [
        (None, True, StudioRule.MODEL_NOT_ON_PLAN),
        (model("m", enabled=False), True, StudioRule.MODEL_NOT_ON_PLAN),
        (dear, False, StudioRule.MODEL_NOT_ON_PLAN),
        (blind, True, StudioRule.MODEL_CANT_DO_ROLE),
    ]

    for candidate, plan, rule in cases:
        with pytest.raises(StudioRuleError) as raised:
            checked_settings(role, settings(), candidate, frontier_on_plan=plan)
        assert raised.value.rule is rule
    with pytest.raises(StudioRuleError) as too_many:
        checked_settings(role, settings(max_tokens=40_000), dear, frontier_on_plan=True)
    assert too_many.value.params == {"min": 256, "max": 16_384}


def test_reasoning_is_stored_off_for_a_model_that_cannot_reason() -> None:
    stored = checked_settings(
        PromptRole.CODE, settings(temperature=Decimal("0.333")), model("m"), frontier_on_plan=False
    )

    assert (stored.reasoning, stored.temperature) == (False, Decimal("0.33"))


def test_without_a_model_only_the_output_limit_is_checked() -> None:
    stored = checked_settings(
        PromptRole.NOTES, settings(model_id=None), None, frontier_on_plan=False
    )

    assert stored.model_id is None
    with pytest.raises(StudioRuleError):
        checked_settings(
            PromptRole.NOTES, settings(model_id=None, max_tokens=100), None, frontier_on_plan=False
        )


def test_a_call_is_asked_within_the_models_own_limits() -> None:
    mute = model("m", supports_temperature=False, max_output_tokens=1_000)

    asked = call_settings(mute, default_settings(PromptRole.NOTES))

    assert (asked.temperature, asked.max_tokens, asked.reasoning) == (None, 1_000, False)
    assert default_settings(PromptRole.CODE).max_tokens == 4_096

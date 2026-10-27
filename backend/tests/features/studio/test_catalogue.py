"""A catalogue model, its defaults and the tier its price proposes (ST-D3, ST-D4, ADR 0074)."""

from dataclasses import replace
from decimal import Decimal
from typing import TypedDict, Unpack

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.studio.domain.catalogue import (
    SLUG_MAX,
    Listing,
    capabilities_of,
    confirmed,
    declined,
    listed,
    priced_tier,
    proposed,
    slug_of,
)
from shosai.features.studio.domain.defaults import RoleDefault, checked_default, held_by
from shosai.features.studio.domain.errors import StudioRule, StudioRuleError
from shosai.features.studio.domain.roles import TEXT, TEXT_AND_VISION, ModelRole, Tier
from tests.features.studio.catalogue_kit import model

LINE = Decimal(6)


class ListingChanges(TypedDict, total=False):
    """The fields of a listing a test may set."""

    name: str
    max_output_tokens: int | None
    input_modalities: frozenset[str]
    output_modalities: frozenset[str]


def listing(**changes: Unpack[ListingChanges]) -> Listing:
    """OpenRouter's entry of a text and image model."""
    base = Listing(
        openrouter_id="anthropic/claude-sonnet-4.5",
        name="Anthropic: Claude Sonnet 4.5",
        context_length=1_000_000,
        max_output_tokens=64_000,
        input_modalities=frozenset({"text", "image"}),
        output_modalities=frozenset({"text"}),
        parameters=frozenset({"temperature", "reasoning", "tools"}),
    )
    return replace(base, **changes)


@given(st.text(alphabet=st.characters(codec="ascii"), min_size=1, max_size=300))
def test_a_slug_is_url_safe_short_and_tells_ids_apart(openrouter_id: str) -> None:
    if not any(char.isalnum() for char in openrouter_id):
        with pytest.raises(ValueError, match="нет букв"):
            slug_of(openrouter_id)
        return
    slug = slug_of(openrouter_id)

    assert 1 <= len(slug) <= SLUG_MAX
    assert set(slug) <= set("abcdefghijklmnopqrstuvwxyz0123456789-")
    assert slug_of(openrouter_id + "x" * 80) != slug_of(openrouter_id + "y" * 80)


def test_a_listed_model_takes_its_description_from_openrouter_and_starts_switched_off() -> None:
    entry = listed(listing(), Tier.STANDARD)

    assert (entry.id, entry.maker, entry.name) == (
        "anthropic-claude-sonnet-4-5",
        "Anthropic",
        "Claude Sonnet 4.5",
    )
    assert entry.capabilities == TEXT_AND_VISION
    assert (entry.supports_temperature, entry.supports_reasoning) == (True, True)
    assert (entry.max_output_tokens, entry.output_limit) == (64_000, 32_768)
    assert not entry.enabled


def test_what_a_model_reads_comes_from_its_modalities() -> None:
    assert capabilities_of(listing(input_modalities=frozenset({"text"}))) == TEXT
    assert capabilities_of(listing(output_modalities=frozenset({"image"}))) == frozenset()


def test_a_name_without_a_maker_takes_the_maker_from_the_id() -> None:
    entry = listed(listing(name="Sonnet", max_output_tokens=None), Tier.STANDARD)

    assert (entry.maker, entry.name, entry.max_output_tokens) == ("anthropic", "Sonnet", 1_000_000)


@pytest.mark.parametrize(
    ("price", "tier"),
    [(None, None), (Decimal("0.000006"), Tier.STANDARD), (Decimal("0.0000061"), Tier.FRONTIER)],
)
def test_the_output_price_proposes_the_tier_above_the_line(
    price: Decimal | None, tier: Tier | None
) -> None:
    assert priced_tier(price, LINE) is tier


def test_a_proposal_waits_for_the_admin_and_a_declined_one_is_not_raised_again() -> None:
    entry = model("m")

    waiting = proposed(entry, Tier.FRONTIER)
    set_aside = declined(waiting)

    assert (waiting.tier, waiting.tier_proposed) == (Tier.STANDARD, Tier.FRONTIER)
    assert proposed(set_aside, Tier.FRONTIER) == set_aside
    assert confirmed(waiting).tier is Tier.FRONTIER
    assert confirmed(waiting).tier_proposed is None
    assert proposed(set_aside, Tier.STANDARD).tier_declined is None
    assert proposed(waiting, None) == waiting


def test_a_default_is_switched_on_standard_and_able_to_serve_its_role() -> None:
    leo, blind = ModelRole.LEO, model("blind")
    seeing = model("seeing", capabilities=TEXT_AND_VISION)
    refused = {
        "missing": (None, StudioRule.MODEL_NOT_FOUND),
        "off": (model("off", enabled=False), StudioRule.MODEL_DISABLED),
        "dear": (
            model("dear", tier=Tier.FRONTIER, capabilities=TEXT_AND_VISION),
            StudioRule.DEFAULT_NOT_STANDARD,
        ),
        "blind": (blind, StudioRule.MODEL_CANT_DO_ROLE),
    }

    for candidate, rule in refused.values():
        with pytest.raises(StudioRuleError) as raised:
            checked_default(leo, candidate)
        assert raised.value.rule is rule
    with pytest.raises(StudioRuleError) as same:
        checked_default(leo, seeing, "seeing", seeing)

    assert same.value.rule is StudioRule.FALLBACK_SAME_AS_DEFAULT
    assert checked_default(ModelRole.CODE, blind) == RoleDefault(ModelRole.CODE, "blind")
    assert checked_default(leo, seeing, "other", model("other", capabilities=TEXT_AND_VISION)) == (
        RoleDefault(leo, "seeing", "other")
    )


def test_a_model_a_default_holds_is_known() -> None:
    defaults = [RoleDefault(ModelRole.CODE, "a", "b")]

    assert held_by("b", defaults)
    assert not held_by("c", defaults)

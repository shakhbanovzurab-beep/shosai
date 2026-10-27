"""Which model answers a role for a person (studio plan §3.3, ADR 0074)."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.studio.domain.catalogue import CatalogueModel
from shosai.features.studio.domain.defaults import RoleDefault
from shosai.features.studio.domain.roles import (
    REQUIRED,
    TEXT_AND_VISION,
    Capability,
    ModelRole,
    Tier,
)
from shosai.features.studio.domain.routing import (
    RoleUnservedError,
    Substitution,
    allowance_used,
    pick,
    refusal,
    route_models,
)
from tests.features.studio.catalogue_kit import catalogue, catalogue_models, model

DEFAULT = model("default", capabilities=TEXT_AND_VISION)
FALLBACK = model("fallback", capabilities=TEXT_AND_VISION)
needs_sets = st.sampled_from([frozenset[Capability](), frozenset({Capability.VISION})])


@st.composite
def worlds(draw: st.DrawFn) -> tuple[list[CatalogueModel], str | None]:
    """A catalogue of any models besides the defaults, and a choice among them or none."""
    others = [draw(catalogue_models(f"m{index}")) for index in range(draw(st.integers(0, 4)))]
    choices = [None, "missing", *(item.id for item in others), DEFAULT.id]
    return [DEFAULT, FALLBACK, *others], draw(st.sampled_from(choices))


@given(
    world=worlds(),
    role=st.sampled_from(ModelRole),
    needs=needs_sets,
    frontier_on_plan=st.booleans(),
)
def test_a_resolved_route_never_names_a_model_that_may_not_answer(
    *,
    world: tuple[list[CatalogueModel], str | None],
    role: ModelRole,
    needs: frozenset[Capability],
    frontier_on_plan: bool,
) -> None:
    models, choice = world
    view = catalogue(models, {role: RoleDefault(role, DEFAULT.id, FALLBACK.id)})

    chosen = pick(role, choice, needs, view, frontier_on_plan=frontier_on_plan)
    route = route_models(chosen, role, needs, view)

    for item in (route.primary, *route.fallbacks):
        assert refusal(item, role, needs, frontier_on_plan=frontier_on_plan) is None
        assert item.usable
        assert item.can(REQUIRED[role] | needs)
    if route.primary.tier is Tier.FRONTIER:
        assert frontier_on_plan
        assert route.fallbacks == ()
        assert route.standard is not None
        assert route.standard.tier is Tier.STANDARD
    else:
        assert all(item.tier is Tier.STANDARD for item in route.fallbacks)
        assert route.primary.id not in {item.id for item in route.fallbacks}
        assert route.standard is None
    honoured = chosen.substitution is None
    assert honoured == (choice is None or route.primary.id == choice)


@given(role=st.sampled_from(ModelRole), needs=needs_sets)
def test_a_frontier_choice_whose_week_is_used_up_gives_way_to_the_default(
    *, role: ModelRole, needs: frozenset[Capability]
) -> None:
    view = catalogue([DEFAULT, FALLBACK], {role: RoleDefault(role, DEFAULT.id, FALLBACK.id)})

    chosen = allowance_used(role, needs, view)

    assert chosen.model == DEFAULT
    assert chosen.substitution is Substitution.FRONTIER_ALLOWANCE_USED


def test_each_reason_a_choice_is_replaced() -> None:
    role = ModelRole.SCREENSHOTS
    models = [
        DEFAULT,
        model("off", enabled=False),
        model("gone", retired=True),
        model("blind"),
        model("dear", tier=Tier.FRONTIER, capabilities=TEXT_AND_VISION),
    ]
    view = catalogue(models, {role: RoleDefault(role, DEFAULT.id)})
    expected = {
        "missing": Substitution.NOT_LISTED,
        "gone": Substitution.NOT_LISTED,
        "off": Substitution.DISABLED,
        "blind": Substitution.CANT_DO_ROLE,
        "dear": Substitution.NOT_ON_PLAN,
    }

    found = {
        choice: pick(role, choice, frozenset(), view, frontier_on_plan=False).substitution
        for choice in expected
    }

    assert found == expected


def test_the_fallback_answers_when_the_default_cannot() -> None:
    role = ModelRole.LEO
    view = catalogue(
        [model("default"), FALLBACK], {role: RoleDefault(role, "default", FALLBACK.id)}
    )

    chosen = pick(role, None, frozenset({Capability.VISION}), view, frontier_on_plan=True)

    assert chosen.model == FALLBACK


def test_a_role_without_a_default_is_not_configured() -> None:
    with pytest.raises(RoleUnservedError) as raised:
        pick(ModelRole.NOTES, None, frozenset(), catalogue([DEFAULT]), frontier_on_plan=True)

    assert raised.value.role is ModelRole.NOTES


def test_a_persons_valid_choice_answers_even_before_the_role_has_a_default() -> None:
    choice = model("mine")

    chosen = pick(ModelRole.CODE, "mine", frozenset(), catalogue([choice]), frontier_on_plan=False)
    route = route_models(chosen, ModelRole.CODE, frozenset(), catalogue([choice]))

    assert (route.primary, route.fallbacks, route.standard) == (choice, (), None)

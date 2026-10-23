"""Toolset routing and card friction before decisions binds its ports (ADR 0068 AG-D7)."""

from hypothesis import given
from hypothesis import strategies as st

from shosai.core.agent_tools.context import Taint
from shosai.core.agent_tools.spec import Reversibility
from shosai.features.agent.domain.friction import (
    Friction,
    combine,
    friction_rule,
    screen_only,
)
from shosai.features.agent.domain.routing import (
    CORE,
    RouteFacts,
    ToolsetFacts,
    route,
    sticky_toolsets,
)

NAMES = ["core", "notes", "tasks", "files", "account", "web", "mail", "calendar"]
TOOLSETS = st.lists(
    st.builds(
        ToolsetFacts,
        name=st.sampled_from(NAMES),
        schema_tokens=st.integers(min_value=50, max_value=2_500),
        allowed=st.booleans(),
    ),
    max_size=8,
    unique_by=lambda toolset: toolset.name,
)


@given(TOOLSETS, st.frozensets(st.sampled_from(NAMES)), st.frozensets(st.sampled_from(NAMES)))
def test_routing_offers_only_what_the_person_may_use_and_names_the_rest(
    toolsets: list[ToolsetFacts], surface: frozenset[str], sticky: frozenset[str]
) -> None:
    facts = RouteFacts(tuple(toolsets), surface=surface, sticky=sticky)
    chosen = route(facts)
    allowed = {toolset.name for toolset in toolsets if toolset.allowed}
    size = {toolset.name: toolset.schema_tokens for toolset in toolsets}
    wanted = ({CORE} | surface | sticky) & allowed

    assert set(chosen.selected).isdisjoint(chosen.deferred)
    assert set(chosen.selected) | set(chosen.deferred) == allowed
    assert wanted <= set(chosen.selected)
    if sum(size[name] for name in wanted) <= facts.cap:
        assert sum(size[name] for name in chosen.selected) <= facts.cap


def test_core_and_the_page_come_first_and_others_fill_the_room_in_order() -> None:
    facts = RouteFacts(
        (
            ToolsetFacts("core", 600),
            ToolsetFacts("notes", 1_500),
            ToolsetFacts("tasks", 1_400),
            ToolsetFacts("files", 1_200),
            ToolsetFacts("account", 300),
            ToolsetFacts("web", 400, allowed=False),
        ),
        surface=frozenset({"tasks"}),
    )

    chosen = route(facts)

    assert chosen.selected == ("core", "notes", "tasks", "account")
    assert chosen.deferred == ("files",)


def test_sticky_toolsets_are_the_last_three_turns() -> None:
    recent = [frozenset({"notes"}), frozenset(), frozenset({"tasks"}), frozenset({"files"})]

    assert sticky_toolsets(recent) == {"notes", "tasks"}


@given(
    st.sampled_from(Taint), st.sampled_from(Reversibility), st.none() | st.sampled_from(Friction)
)
def test_friction_is_never_below_the_rule(
    taint: Taint, reversibility: Reversibility, judged: Friction | None
) -> None:
    rule = friction_rule(taint, reversibility)
    card = combine(rule, judged)

    assert card >= rule
    assert (rule is Friction.WARNING) == (
        taint >= Taint.EXTERNAL or reversibility is Reversibility.IRREVERSIBLE
    )
    assert screen_only(card) == (card >= Friction.WARNING)

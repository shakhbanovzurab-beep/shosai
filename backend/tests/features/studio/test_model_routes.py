"""The model of a role for a person (studio step 10, plan §3.3): the choice or the default with
its reason, frontier only on the plan and within the week, spent tokens stopping the call, a
role without a default refused and counted, and one statement of the person's row."""

import time

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

from shosai.core.ai.calls import CallClass, ModelRef, Provider
from shosai.core.ai.requests import ReasoningEffort
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.billing.contracts import ModelTier, TokenDecision, TokenLimit, TokenRoute
from shosai.features.studio.contracts import (
    ModelRoleUnconfiguredError,
    ResolvedRoute,
    RoutePerson,
    TokenLimitError,
)
from shosai.features.studio.domain.roles import ModelCapability, ModelRole, Tier
from shosai.features.studio.domain.routing import Substitution
from shosai.features.studio.infrastructure.route_metrics import SUBSTITUTIONS, UNCONFIGURED
from tests.features.studio.catalogue_bench import catalogue_bench, person
from tests.features.studio.resolution_kit import (
    FLASH,
    MINI,
    SMALL,
    SONNET,
    Resolution,
    resolution,
    settings_row,
)
from tests.harness.database_access import DatabaseAccess


async def routed(bench: Resolution, who: RoutePerson, role: ModelRole, chosen: str | None = None,
                 needs: frozenset[ModelCapability] = frozenset()) -> ResolvedRoute:  # fmt: skip
    """One resolution in the person's transaction."""
    async with bench.catalogue.homes.transactions.begin(
        TenancyScope(who.home, who.user_id)
    ) as session:
        return await bench.routes.route(session, who, role, chosen, needs)


@pytest.fixture
async def bench(homes: DatabaseAccess) -> Resolution:
    """Four models and defaults for five roles over the slot's homes."""
    return await resolution(catalogue_bench(homes))


async def test_an_unset_role_answers_with_its_default_and_its_fallback(bench: Resolution) -> None:
    route = await routed(bench, person(), ModelRole.LIVE_ANSWERS)

    assert route.route.primary == ModelRef(Provider.OPENROUTER, FLASH)
    assert route.route.fallbacks == (ModelRef(Provider.OPENROUTER, MINI),)
    assert (route.call_class, route.temperature, route.max_tokens, route.substitution) == (
        CallClass.STANDARD, 0.7, 4_096, None,
    )  # fmt: skip
    assert route.route.reasoning is ReasoningEffort.MINIMAL


async def test_the_person_s_choice_answers_with_their_settings(bench: Resolution) -> None:
    who = person()
    await settings_row(who, "code", bench.ids[MINI], reasoning=True, bench=bench.catalogue)

    route = await routed(bench, who, ModelRole.CODE)

    assert route.route.primary == ModelRef(Provider.OPENROUTER, MINI)
    assert route.route.fallbacks == (ModelRef(Provider.OPENROUTER, FLASH),)
    assert (route.temperature, route.max_tokens, route.reasoning) == (0.3, 2_000, False)


async def test_a_choice_that_may_not_answer_gives_way_to_the_default_with_its_reason(
    bench: Resolution,
) -> None:
    who = person()
    await settings_row(who, "screenshots", bench.ids[SMALL], bench=bench.catalogue)
    await settings_row(who, "code", bench.ids[SONNET], bench=bench.catalogue)

    blind = await routed(bench, who, ModelRole.SCREENSHOTS)
    off_plan = await routed(bench, who, ModelRole.CODE)

    assert (blind.model_id, blind.substitution) == (bench.ids[FLASH], Substitution.CANT_DO_ROLE)
    assert (off_plan.model_id, off_plan.substitution) == (
        bench.ids[FLASH],
        Substitution.NOT_ON_PLAN,
    )
    assert bench.counted(SUBSTITUTIONS, studio_role="code", reason="not_on_plan") == 1


async def test_frontier_answers_alone_within_the_week_and_gives_way_after_it(
    bench: Resolution,
) -> None:
    who = person(frontier=True)
    await settings_row(who, "code", bench.ids[SONNET], bench=bench.catalogue)

    within = await routed(bench, who, ModelRole.CODE)
    bench.allowance.decisions[ModelTier.FRONTIER] = TokenDecision(
        TokenRoute.FALL_BACK, TokenLimit.FRONTIER_WEEK
    )
    after = await routed(bench, who, ModelRole.CODE)

    assert (within.tier, within.call_class, within.route.fallbacks) == (
        Tier.FRONTIER,
        CallClass.EXPENSIVE,
        (),
    )
    assert within.route.standard == ModelRef(Provider.OPENROUTER, FLASH)
    assert (after.model_id, after.substitution) == (
        bench.ids[FLASH],
        Substitution.FRONTIER_ALLOWANCE_USED,
    )
    assert bench.allowance.asked == [ModelTier.FRONTIER, ModelTier.FRONTIER, ModelTier.STANDARD]


async def test_spent_standard_tokens_stop_and_a_role_without_a_default_is_refused(
    bench: Resolution,
) -> None:
    bench.allowance.decisions[ModelTier.STANDARD] = TokenDecision(
        TokenRoute.STOP, TokenLimit.STANDARD_WEEK
    )

    with pytest.raises(TokenLimitError) as stopped:
        await routed(bench, person(), ModelRole.NOTES)
    with pytest.raises(ModelRoleUnconfiguredError):
        await routed(bench, person(), ModelRole.SYSTEM_DESIGN)

    assert (stopped.value.code, stopped.value.params) == (
        "token_limit",
        {"limit": "standard_weekly_tokens"},
    )
    assert bench.counted(UNCONFIGURED, studio_role="system_design") == 1


async def test_leo_takes_its_model_from_settings_and_a_picture_needs_vision(
    bench: Resolution,
) -> None:
    chosen = await routed(bench, person(), ModelRole.LEO, bench.ids[MINI])
    blind = await routed(
        bench, person(), ModelRole.LEO, bench.ids[SMALL], frozenset({ModelCapability.VISION})
    )

    assert (chosen.model_id, chosen.route.reasoning) == (bench.ids[MINI], None)
    assert (blind.model_id, blind.substitution) == (bench.ids[FLASH], Substitution.CANT_DO_ROLE)


async def test_a_resolution_reads_one_row_and_its_p95_is_recorded(bench: Resolution) -> None:
    who = person()
    await settings_row(who, "code", bench.ids[MINI], bench=bench.catalogue)
    await routed(bench, who, ModelRole.CODE)
    statements: list[str] = []

    def counted(*args: object) -> None:
        statements.append(str(args[2]))

    event.listen(Engine, "before_cursor_execute", counted)
    try:
        await routed(bench, who, ModelRole.CODE)
    finally:
        event.remove(Engine, "before_cursor_execute", counted)
    timings = []
    for _ in range(200):
        started = time.perf_counter()
        await routed(bench, who, ModelRole.CODE)
        timings.append(time.perf_counter() - started)
    p95 = sorted(timings)[189]

    # Настройки транзакции и одна строка человека; каталог — из снимка процесса.
    person_reads = [sql for sql in statements if "model_role_assignments" in sql]
    assert len(person_reads) == 1, statements
    assert p95 < 0.05, p95

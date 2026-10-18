"""Leo's `account.get_plan` and `account.get_usage` read the run's person only (step 7)."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from shosai.core.agent_tools.bindings import ReadTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import ToolErrorCode
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.application.minutes import MinutesMeter
from shosai.features.billing.application.people_views import PeopleViews
from shosai.features.billing.application.tokens import TokenStanding
from shosai.features.billing.channels.agent_tools import (
    NoArguments,
    PlanOutput,
    UsageOutput,
    billing_tools,
)
from shosai.features.billing.domain.meters import TokenLimit, TokenRoute
from shosai.features.billing.domain.plans import ModelTier
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER
from tests.features.billing.catalogue_bench import created, plan_draft
from tests.features.billing.entitlement_bench import EntitlementBench
from tests.features.billing.people_bench import Countries
from tests.features.billing.test_tokens import LIMITS, row, writer


def tools(
    bench: EntitlementBench, *, transactions_down: bool = False
) -> tuple[ReadTool[NoArguments, PlanOutput], ReadTool[NoArguments, UsageOutput]]:
    """The plan and usage tools over the bench, or over a database out of reach."""
    ports = PortDirectory()
    ports.install([ACCOUNT_PROFILE_READER.bind(Countries())])
    transactions = bench.unreachable() if transactions_down else bench.homes.transactions
    snapshots = bench.without_database() if transactions_down else bench.snapshots
    meter = MinutesMeter(transactions, (snapshots, ports), bench.clock)
    views = PeopleViews(transactions, (snapshots, meter, ports), bench.clock)
    standing = TokenStanding(transactions, snapshots, bench.clock)
    return billing_tools(views, standing)


def context(home: Home, user_id: UUID) -> ToolContext:
    return ToolContext(
        scope=TenancyScope(home, user_id),
        run_id=uuid4(),
        deadline=datetime.now(UTC) + timedelta(seconds=30),
    )


async def test_the_plan_and_usage_tools_read_the_run_s_person(
    entitlements: EntitlementBench,
) -> None:
    person = (Home.EU, uuid4())
    plan = await created(
        entitlements.catalogue, "/v1/admin/plans", plan_draft("pro", limits=LIMITS)
    )
    await entitlements.subscribe(person, (plan, "pro"))
    await writer(entitlements).write(row(person, entitlements.clock.now, 1000))
    plan_tool, usage_tool = tools(entitlements)

    planned = (await plan_tool.run(NoArguments(), context(*person))).output
    used = (await usage_tool.run(NoArguments(), context(*person))).output

    assert planned is not None
    assert used is not None
    assert planned.plan_name == "Pro"
    assert (planned.paid, planned.meeting_minutes_per_month) == (True, None)
    tiers = {tier.tier: tier for tier in used.tiers}
    assert tiers[ModelTier.FRONTIER].used_tokens == 1000
    assert tiers[ModelTier.FRONTIER].next_request is TokenRoute.FALL_BACK
    assert tiers[ModelTier.FRONTIER].limit_reached is TokenLimit.FRONTIER_WEEK
    assert tiers[ModelTier.STANDARD].next_request is TokenRoute.WITHIN_ALLOWANCE
    assert used.pack_tokens_left == 0


async def test_without_the_database_the_tools_say_unavailable(
    entitlements: EntitlementBench,
) -> None:
    plan_tool, _ = tools(entitlements, transactions_down=True)

    result = await plan_tool.run(NoArguments(), context(Home.RU, uuid4()))

    assert result.error is not None
    assert result.error.code is ToolErrorCode.UNAVAILABLE

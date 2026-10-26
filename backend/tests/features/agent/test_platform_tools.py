"""The operator's `platform` toolset (agent step 16a): F6's spend reports, the OpenRouter balance
and the counts of answer ratings as numbers with their report as a source, for the platform
operator alone; ratings counted across both homes and every person, by model, never more."""

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

import pytest

from shosai.core.agent_tools.bindings import ReadTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import ToolErrorCode
from shosai.core.agent_tools.sources import SourceKind
from shosai.core.ai.spend.operator import SpendOperator
from shosai.core.ai.spend.reports import DailyRow, Forecast, ReportPeriod, SummaryGroup, SummaryRow
from shosai.core.ai.spend.standing import Credits
from shosai.core.config.roles import ProcessRole
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.platform_ratings import PlatformRatings
from shosai.features.agent.channels.platform_reads import PlatformReads
from shosai.features.agent.channels.platform_specs import DaysIn, NothingIn, SpendSummaryIn
from shosai.features.agent.channels.platform_tools import platform_tools
from shosai.features.agent.domain.operator import operator_scope
from shosai.features.agent.domain.spaces import space_of
from shosai.features.agent.infrastructure.person_records import AgentFeedbackRecord
from shosai.features.agent.infrastructure.run_records import AgentRunRecord
from shosai.features.agent.infrastructure.thread_records import AgentThreadRecord
from shosai.features.billing.contracts import COMMERCE_FACTS, PlanSummary, PromoSummary
from shosai.features.identity.contracts.accounts import ACCOUNT_COUNTS, HomeAccounts
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot

NOW = datetime(2026, 10, 26, 12, tzinfo=UTC)


@dataclass
class Reports:
    """F6's reports, as the tools read them."""

    asked: list[tuple[SummaryGroup, ReportPeriod]]

    async def summary(
        self, group: SummaryGroup, period: ReportPeriod, at: datetime
    ) -> tuple[SummaryRow, ...]:
        self.asked.append((group, period))
        return (
            SummaryRow("google/gemini", 12, Decimal("1.234"), Decimal("101.5"), 0),
            SummaryRow("anthropic/haiku", 3, Decimal("0.5"), Decimal("41"), 1),
        )

    async def daily(self, at: datetime, days: int = 30) -> tuple[DailyRow, ...]:
        return (
            DailyRow(date(2026, 10, 25), "openrouter", "a", 2, 10, 5, 0, Decimal("0.2")),
            DailyRow(date(2026, 10, 25), "openrouter", "b", 1, 10, 5, 0, Decimal("0.3")),
            DailyRow(date(2026, 10, 26), "openrouter", "a", 4, 10, 5, 0, Decimal("0.4")),
        )

    async def forecast(self, at: datetime) -> Forecast:
        return Forecast(Decimal("10"), Decimal("31"), Decimal("10"), 31)


@dataclass
class Balance:
    """OpenRouter's credits, or none without the management key."""

    credits_left: Credits | None

    async def credits(self) -> Credits | None:
        return self.credits_left


def plan(slug: str, subscribers: int, month: dict[str, int]) -> PlanSummary:
    """A plan on sale."""
    return PlanSummary(
        slug=slug, name=slug.title(), audience="individual", subscribers=subscribers,
        on_sale=True, archived=False, month_prices=month, year_prices={},
    )  # fmt: skip


class Commerce:
    """Billing's plans and promo codes."""

    async def plans(self) -> list[PlanSummary]:
        return [
            plan("free", 40, {}),
            plan("pro", 7, {"USD": 1500, "RUB": 149000, "EUR": 1400}),
        ]  # fmt: skip

    async def promo_codes(self) -> list[PromoSummary]:
        return [PromoSummary("SPRING", "active", 20, 3, 100, date(2026, 11, 30))]


class Accounts:
    """Identity's counts of both homes."""

    async def counts(self, days: int) -> list[HomeAccounts]:
        return [
            HomeAccounts(Home.RU, {"active": 30, "frozen": 1}, days),
            HomeAccounts(Home.EU, {"active": 50}, 2),
        ]


def tools(
    reports: Reports, balance: Balance, ratings: PlatformRatings
) -> dict[str, ReadTool[Any, Any]]:
    spend = SpendOperator(
        cast("Any", reports), cast("Any", None), cast("Any", balance), cast("Any", None)
    )
    ports = PortDirectory()
    ports.install([COMMERCE_FACTS.bind(Commerce()), ACCOUNT_COUNTS.bind(Accounts())])
    bound = platform_tools(PlatformReads((spend, ratings, ports), clock=lambda: NOW))
    return {tool.spec.name: cast("ReadTool[Any, Any]", tool) for tool in bound}


def context(scope: TenancyScope) -> ToolContext:
    return ToolContext(scope, uuid.uuid4(), datetime.now(UTC) + timedelta(minutes=1))


async def test_spend_is_read_from_f6_s_reports_and_names_its_report(homes: DatabaseAccess) -> None:
    reports = Reports([])
    found = tools(
        reports,
        Balance(Credits(Decimal(50), Decimal("12.345"))),
        PlatformRatings(homes.transactions),
    )
    operator = context(operator_scope())

    summary = await found["platform.spend_summary"].run(
        SpendSummaryIn(period="month", group="model"), operator
    )
    daily = await found["platform.spend_daily"].run(DaysIn(days=2), operator)
    forecast = await found["platform.spend_forecast"].run(NothingIn(), operator)
    balance = await found["platform.openrouter_balance"].run(NothingIn(), operator)

    assert reports.asked == [(SummaryGroup.MODEL, ReportPeriod.MONTH)]
    assert summary.output is not None
    assert (summary.output.total_usd, summary.output.rows[0].cost_usd) == (1.73, 1.23)
    assert [(s.kind, s.id) for s in summary.sources] == [
        (SourceKind.REPORT, "spend.summary:month:model")
    ]
    assert space_of(summary.sources[0], "ru", {}) == "Платформа"
    assert daily.output is not None
    assert [(d.day, d.calls, d.cost_usd) for d in daily.output.days] == [
        ("2026-10-25", 3, 0.5), ("2026-10-26", 4, 0.4),
    ]  # fmt: skip
    assert [m.key for m in daily.output.top_models] == ["a", "b"]
    assert forecast.output is not None
    assert forecast.output.projected_usd == 31.0
    assert balance.output is not None
    assert balance.output.left_usd == 37.66


async def test_no_balance_without_the_key_and_no_caller_but_the_operator(
    homes: DatabaseAccess,
) -> None:
    found = tools(Reports([]), Balance(None), PlatformRatings(homes.transactions))
    person = context(TenancyScope(Home.EU, uuid.uuid4()))

    balance = found["platform.openrouter_balance"]
    missing = await balance.run(NothingIn(), context(operator_scope()))
    others = [tool for tool in found.values() if tool.spec.name != "platform.spend_summary"]
    refused = [await tool.run(tool.spec.input.model_validate({}), person) for tool in others]

    assert missing.error is not None
    assert missing.error.code is ToolErrorCode.UNAVAILABLE
    assert {r.error.code for r in refused if r.error is not None} == {ToolErrorCode.FORBIDDEN}
    assert len(refused) == 7


@pytest.mark.parametrize("home", [Home.RU, Home.EU])
async def test_ratings_are_counted_across_people_by_model(
    homes: DatabaseAccess, run_slot: RunSlot, home: Home
) -> None:
    now = datetime.now(UTC)
    for rating, model in (("useful", "a"), ("useful", "a"), ("not_useful", None)):
        person = uuid.uuid4()
        thread, run = uuid.uuid4(), uuid.uuid4()
        async with homes.transactions.begin(TenancyScope(home, person)) as session:
            session.add(AgentThreadRecord(id=thread, user_id=person, scope_kind="personal",
                                          last_activity_at=now, created_at=now,
                                          updated_at=now))  # fmt: skip
            await session.flush()
            session.add(AgentRunRecord(id=run, user_id=person, thread_id=thread, channel="web",
                                       status="completed", started_at=now, ended_at=now,
                                       outcome_code="answered", model=model))  # fmt: skip
            session.add(AgentFeedbackRecord(message_id=uuid.uuid4(), user_id=person,
                                            thread_id=thread, run_id=run, rating=rating,
                                            created_at=now, updated_at=now))  # fmt: skip
    # Счёт оценок — обход только на чтение; инструменты оператора идут в воркерах очереди agent.
    workers = ProcessShape(role=ProcessRole.WORKERS)
    async with open_database_access(slot_urls(run_slot), workers) as access:
        found = tools(Reports([]), Balance(None), PlatformRatings(access.transactions))
        rated = await found["platform.answer_ratings"].run(
            DaysIn(days=7), context(operator_scope())
        )

    assert rated.output is not None
    assert (rated.output.useful, rated.output.not_useful) == (2, 1)
    assert [(line.model, line.useful, line.not_useful) for line in rated.output.by_model] == [
        ("a", 2, 0), ("unknown", 0, 1),
    ]  # fmt: skip


async def test_plans_promo_codes_and_accounts_come_through_their_owners_ports(
    homes: DatabaseAccess,
) -> None:
    found = tools(Reports([]), Balance(None), PlatformRatings(homes.transactions))
    operator = context(operator_scope())

    plans = await found["platform.plans"].run(NothingIn(), operator)
    codes = await found["platform.promo_codes"].run(NothingIn(), operator)
    accounts = await found["platform.accounts"].run(DaysIn(days=30), operator)

    assert plans.output is not None
    assert plans.output.plans[1].month_prices == {"USD": 15.0, "RUB": 1490.0, "EUR": 14.0}
    assert [(a.kind.value, a.ref, a.alt) for a in plans.artifacts] == [
        ("chart", "chart:billing.plans", "Подписчики по тарифам")
    ]
    assert codes.output is not None
    assert codes.output.promo_codes[0].valid_until == "2026-11-30"
    assert accounts.output is not None
    assert [(h.home, h.registered) for h in accounts.output.homes] == [("ru", 30), ("eu", 2)]
    spec = json.loads(accounts.artifacts[0].fields["spec"])
    assert spec["rows"] == [
        {"home": "RU", "active": 30, "registered": 30},
        {"home": "EU", "active": 50, "registered": 2},
    ]  # fmt: skip
    assert [s["label"] for s in spec["series"]] == ["Активные", "Новые за 30 дн."]


async def test_a_series_comes_with_its_chart_computed_from_the_same_rows(
    homes: DatabaseAccess,
) -> None:
    found = tools(Reports([]), Balance(None), PlatformRatings(homes.transactions))

    daily = await found["platform.spend_daily"].run(DaysIn(days=2), context(operator_scope()))

    [drawn] = daily.artifacts
    spec = json.loads(drawn.fields["spec"])
    assert (drawn.ref, drawn.alt) == ("chart:spend.daily:2", "Расходы на ИИ по дням, 2 дн.")
    assert (spec["shape"], spec["x"], spec["stacked"]) == ("line", "day", False)
    assert spec["rows"] == [
        {"day": "2026-10-25", "cost_usd": 0.5}, {"day": "2026-10-26", "cost_usd": 0.4},
    ]  # fmt: skip

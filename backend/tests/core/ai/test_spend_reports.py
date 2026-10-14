"""Spend reports sum both homes; the rebuild restores the counters from the cost rows."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import httpx
from redis.asyncio import Redis

from shosai.core.ai.adapters.openrouter import OPENROUTER_API
from shosai.core.ai.calls import PlatformAccount
from shosai.core.ai.costs.entries import CostEntry
from shosai.core.ai.spend.guard import Ceilings
from shosai.core.ai.spend.kill_switch import KillSwitch
from shosai.core.ai.spend.reports import (
    ReportPeriod,
    SpendReports,
    SummaryGroup,
    month_start,
)
from shosai.core.ai.spend.standing import OpenRouterCredits, SpendStanding
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from tests.core.ai.bench import ORG_ID, USER_ID, Doubles, ai_bench
from tests.harness.database_access import DatabaseAccess

OTHER_USER = UUID("0190f0f0-0000-7000-8000-0000000000a2")
BASE = month_start(datetime.now(UTC))
AT = BASE + timedelta(days=2, hours=2)


def row(
    home: Home, at: datetime, cost: str, *, model: str = "probe/chat", **fields: object
) -> CostEntry:
    """A recorded call of a user in a home."""
    values: dict[str, object] = {
        "home": home, "user_id": USER_ID, "org_id": ORG_ID, "cost_id": new_id(),
        "created_at": at, "effect_key": f"report:{new_id().hex}", "provider": "openrouter",
        "model": model, "kind": "chat", "feature": "probe.chat", "call_class": "standard",
        "origin": "interactive", "outcome": "ok", "input_tokens": 100, "output_tokens": 10,
        "cost_usd": Decimal(cost), "cost_source": "reported",
        "exchange_rate_used": Decimal("90.0000"), "cost_rub": Decimal(cost) * 90,
    }  # fmt: skip
    values.update(fields)
    return CostEntry.model_validate(values)


async def seeded(homes: DatabaseAccess) -> SpendReports:
    """Rows in both homes: two today, one earlier this month, one without a rate."""
    writer = ai_bench(homes.transactions).writer
    for entry in (
        row(Home.RU, AT - timedelta(hours=1), "0.30"),
        row(Home.EU, AT - timedelta(minutes=5), "0.20", model="probe/other", feature="leo.turn"),
        row(Home.EU, BASE + timedelta(hours=1), "0.50"),
        row(Home.RU, AT - timedelta(hours=1), "0.10", user_id=OTHER_USER,
            exchange_rate_used=None, cost_rub=None),
    ):  # fmt: skip
        await writer.write(entry)
    return SpendReports(homes.transactions)


async def test_a_summary_adds_up_both_homes(homes: DatabaseAccess) -> None:
    reports = await seeded(homes)

    today = await reports.summary(SummaryGroup.PROVIDER, ReportPeriod.TODAY, AT)
    month = await reports.summary(SummaryGroup.MODEL, ReportPeriod.MONTH, AT)
    features = await reports.summary(SummaryGroup.FEATURE, ReportPeriod.ALL_TIME, AT)

    [provider] = today
    assert (provider.key, provider.calls, provider.cost_usd) == ("openrouter", 3, Decimal("0.60"))
    assert (provider.cost_rub, provider.without_rate) == (Decimal("45.00"), 1)
    assert [(r.key, r.cost_usd) for r in month] == [
        ("probe/chat", Decimal("0.90")), ("probe/other", Decimal("0.20")),
    ]  # fmt: skip
    assert {r.key: r.calls for r in features} == {"probe.chat": 3, "leo.turn": 1}


async def test_a_daily_series_carries_each_model_s_tokens(homes: DatabaseAccess) -> None:
    reports = await seeded(homes)

    series = await reports.daily(AT, days=3)

    by_day = {(r.day, r.model): (r.calls, r.input_tokens, r.cost_usd) for r in series}
    assert by_day[(AT.date(), "probe/chat")] == (2, 200, Decimal("0.40"))
    assert by_day[(AT.date(), "probe/other")] == (1, 100, Decimal("0.20"))
    assert by_day[(BASE.date(), "probe/chat")] == (1, 100, Decimal("0.50"))


async def test_the_forecast_runs_the_month_at_its_pace(homes: DatabaseAccess) -> None:
    reports = await seeded(homes)

    forecast = await reports.forecast(AT)

    elapsed = Decimal(timedelta(days=2, hours=2).total_seconds()) / Decimal(86_400)
    assert forecast.month_to_date_usd == Decimal("1.10")
    assert forecast.projected_usd == (Decimal("1.10") / elapsed * forecast.days_in_month).quantize(
        Decimal("0.01")
    )


async def test_one_person_s_spend_comes_from_their_home(homes: DatabaseAccess) -> None:
    reports = await seeded(homes)

    russian = await reports.user_spend(Home.RU, USER_ID, AT)
    european = await reports.user_spend(Home.EU, USER_ID, AT)

    assert (russian.today_usd, russian.month_usd) == (Decimal("0.30"), Decimal("0.30"))
    assert (european.today_usd, european.month_usd) == (Decimal("0.20"), Decimal("0.70"))
    assert european.today_usd <= european.week_usd <= european.month_usd


async def test_the_openrouter_balance_is_read_once_in_five_minutes() -> None:
    asked: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        asked.append(request.headers["Authorization"])
        return httpx.Response(200, json={"data": {"total_credits": 100.5, "total_usage": 25.75}})

    client = httpx.AsyncClient(
        base_url=OPENROUTER_API + "/",
        headers={"Authorization": "Bearer management"},
        transport=httpx.MockTransport(handle),
    )
    credits = OpenRouterCredits(client)

    first = await credits.credits()
    second = await credits.credits()

    assert first == second
    assert first is not None
    assert first.left_usd == Decimal("74.75")
    assert asked == ["Bearer management"]
    assert await OpenRouterCredits(None).credits() is None


async def test_the_standing_shows_spent_and_reserved_against_each_ceiling(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    writer = ai_bench(homes.transactions, doubles=Doubles(valkey=valkey)).writer
    now = datetime.now(UTC)
    await writer.write(row(Home.EU, now, "0.25"))
    await writer.write(
        row(Home.EU, now, "0.05", user_id=None, org_id=None, platform_account="landing_demo")
    )
    ceilings = Ceilings(
        global_hour=400_000_000, global_day=4_000_000_000,
        platform={account.value: (5_000_000, 20_000_000) for account in PlatformAccount},
    )  # fmt: skip
    standing = await SpendStanding(valkey, ceilings, KillSwitch(valkey, forced=False)).standing(now)

    states = {state.name: state for state in standing.ceilings}
    assert (states["global_day"].spent_usd, states["global_day"].ceiling_usd) == (
        Decimal("0.3"), Decimal(4000),
    )  # fmt: skip
    assert states["landing_demo_hour"].spent_usd == Decimal("0.05")
    assert states["help_assistant_day"].spent_usd == Decimal(0)
    assert standing.kill_switch.engaged is False

"""Weekly tokens per tier, token packs and the route of the next request (step 5, BL-D4)."""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from prometheus_client import CollectorRegistry
from sqlalchemy import insert

from shosai.core.ai.costs.billing import BillingMarks
from shosai.core.ai.costs.entries import CostEntry
from shosai.core.ai.costs.settlement import CostSettlements
from shosai.core.ai.costs.writer import CostWriter
from shosai.core.ai.metrics import AiMetrics
from shosai.core.idempotency.batch import EffectBatch
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.billing.application.tokens import TokenSettlement, TokenStanding, packs_left
from shosai.features.billing.contracts import TokenLimit, TokenRoute
from shosai.features.billing.domain.plans import ModelTier
from shosai.features.billing.infrastructure.token_records import CreditLedgerRecord
from tests.core.ai.bench import RecordingSender, unreachable_valkey
from tests.doubles.business_calendar import MOSCOW
from tests.features.billing.catalogue_bench import created, plan_draft
from tests.features.billing.entitlement_bench import EntitlementBench

LIMITS = {
    "meeting_minutes_per_month": None, "file_manager_gb": 10, "knowledge_base_mb": 10,
    "weekly_standard_tokens": None, "weekly_frontier_tokens": 1000, "daily_standard_tokens": 500,
}  # fmt: skip


def writer(bench: EntitlementBench) -> CostWriter:
    """The cost writer with billing's settlement, as composition installs it."""
    registry = CollectorRegistry()
    settlements = CostSettlements()
    settlements.install([TokenSettlement(bench.snapshots, MOSCOW)])
    keys = EffectKeyMetrics(registry)
    marks = BillingMarks(unreachable_valkey(), registry)
    return CostWriter(
        bench.homes.transactions, (EffectLedger(keys), EffectBatch(keys)), settlements,
        RecordingSender(), (AiMetrics(registry), marks),
    )  # fmt: skip


def row(
    person: tuple[Home, UUID],
    at: datetime,
    tokens: int,
    call: tuple[str, str] = ("expensive", "interactive"),
    model: str = "probe/chat",
) -> CostEntry:
    """A call of `tokens` (input and output halves); `call` is its class and origin."""
    call_class, origin = call
    return CostEntry(
        home=person[0], user_id=person[1], org_id=None, cost_id=new_id(), created_at=at,
        effect_key=f"leo:{uuid4()}", provider="openrouter", model=model, kind="chat",
        feature="agent.turn", outcome="ok", input_tokens=tokens // 2,
        output_tokens=tokens - tokens // 2, cost_usd=Decimal("0.01"), cost_source="reported",
        call_class=call_class, origin=origin,
    )  # fmt: skip


async def subscribed(bench: EntitlementBench, packs: int) -> tuple[Home, UUID]:
    """A person on a plan with 1000 frontier tokens a week and 500 standard a day."""
    person = (Home.RU, uuid4())
    plan = await created(bench.catalogue, "/v1/admin/plans", plan_draft("pro", limits=LIMITS))
    await bench.subscribe(person, (plan, "pro"))
    if packs:
        async with bench.homes.transactions.begin(TenancyScope(*person)) as session:
            purchase = {
                "id": new_id(), "user_id": person[1], "kind": "purchase", "tokens": packs,
                "transaction_id": uuid4(),
            }  # fmt: skip
            await session.execute(insert(CreditLedgerRecord).values(**purchase))
    return person


async def balance(bench: EntitlementBench, person: tuple[Home, UUID]) -> int:
    async with bench.homes.transactions.begin(TenancyScope(*person), read_only=True) as session:
        return await packs_left(session, person[1])


async def test_packs_pay_only_past_the_weekly_allowance_and_a_redelivered_row_debits_once(
    entitlements: EntitlementBench,
) -> None:
    person = await subscribed(entitlements, packs=5000)
    costs, standing = (
        writer(entitlements),
        TokenStanding(
            entitlements.homes.transactions,
            entitlements.snapshots,
            entitlements.clock,
            business=MOSCOW,
        ),
    )
    now = entitlements.clock.now
    await costs.write(row(person, now, 800))
    within = await standing.decision(*person, ModelTier.FRONTIER)
    crossing = row(person, now, 400)
    await costs.write(crossing)
    await costs.write(crossing)
    after_crossing = await balance(entitlements, person)
    from_packs = await standing.decision(*person, ModelTier.FRONTIER)
    await costs.write(row(person, now, 6000))
    fallen = await standing.decision(*person, ModelTier.FRONTIER)

    assert within.route is TokenRoute.WITHIN_ALLOWANCE
    assert after_crossing == 4800
    assert from_packs.route is TokenRoute.FROM_PACKS
    assert await balance(entitlements, person) == 0
    assert (fallen.route, fallen.reason) == (TokenRoute.FALL_BACK, TokenLimit.FRONTIER_WEEK)


async def test_the_standard_day_stops_with_its_reason_and_the_week_resets_on_the_business_monday(
    entitlements: EntitlementBench,
) -> None:
    person = await subscribed(entitlements, packs=0)
    costs, clock = writer(entitlements), entitlements.clock
    standing = TokenStanding(
        entitlements.homes.transactions, entitlements.snapshots, clock, business=MOSCOW
    )
    await costs.write(row(person, clock.now, 500, call=("standard", "interactive")))
    await costs.write(row(person, clock.now, 1000))
    stopped = await standing.decision(*person, ModelTier.STANDARD)
    fallen = await standing.decision(*person, ModelTier.FRONTIER)
    monday = MOSCOW.week_window(clock.now)[1]
    clock.now = monday - timedelta(seconds=1)
    still = await standing.decision(*person, ModelTier.FRONTIER)
    clock.now = monday
    fresh = await standing.decision(*person, ModelTier.FRONTIER)
    day_after = await standing.decision(*person, ModelTier.STANDARD)

    assert (stopped.route, stopped.reason) == (TokenRoute.STOP, TokenLimit.STANDARD_DAY)
    assert fallen.route is TokenRoute.FALL_BACK
    assert still.route is TokenRoute.FALL_BACK
    assert fresh.route is day_after.route is TokenRoute.WITHIN_ALLOWANCE


async def test_meetings_background_work_and_last_week_s_rows_are_not_counted(
    entitlements: EntitlementBench,
) -> None:
    person = await subscribed(entitlements, packs=0)
    costs, now = writer(entitlements), entitlements.clock.now
    standing = TokenStanding(
        entitlements.homes.transactions,
        entitlements.snapshots,
        entitlements.clock,
        business=MOSCOW,
    )
    await costs.write(row(person, now, 5000, call=("essential", "interactive")))
    await costs.write(row(person, now, 5000, call=("expensive", "background")))
    await costs.write(row(person, now, 10))
    await costs.write(row(person, MOSCOW.week_window(now)[0] - timedelta(hours=1), 5000))

    decision = await standing.decision(*person, ModelTier.FRONTIER)

    assert decision.route is TokenRoute.WITHIN_ALLOWANCE

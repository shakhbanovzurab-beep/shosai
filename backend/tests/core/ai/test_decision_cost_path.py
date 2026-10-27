"""A Jev decision never waits for the payer's home: its cost row goes to the record task
(ADR 0069 DL-D2). Counted in round trips through a proxy in front of the Russian home, each
one 30 to 45 ms from the plane on the real link."""

import httpx

from shosai.core.ai.calls import ModelRoute
from shosai.core.kernel.homes import Home
from tests.core.ai.bench import ai_bench, context, set_prices
from tests.core.ai.test_decisions import JEV, SOON, TICKET, recorded
from tests.core.db.tcp_proxy import CountingProxy, Upstream, through
from tests.harness.database_access import DatabaseAccess, open_database_access, slot_urls
from tests.harness.run_slot import RunSlot


async def test_a_decision_makes_no_round_trip_to_the_payers_home(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    await set_prices(homes.transactions, JEV, input_token="0.000000042", output_token="0")
    target = run_slot.claimed.targets(Home.RU).application
    proxy = CountingProxy(Upstream(target.host, target.port))
    port = await proxy.start()
    urls = slot_urls(run_slot)
    urls[Home.RU] = through(urls[Home.RU], port)
    try:
        async with open_database_access(urls) as access:
            await access.gate.verify_at_start()
            bench = ai_bench(access.transactions)
            bench.openrouter.answer("alpha/decisions", httpx.Response(200, json=recorded()))
            proxy.reset()

            await bench.providers.decide(
                context("turn:1:route", home=Home.RU, consent=True, deadline=SOON),
                ModelRoute(JEV),
                TICKET,
            )

            assert proxy.turns == 0
            assert [name for name, _ in bench.sender.sent] == ["ai.record_cost"]
    finally:
        await proxy.stop()

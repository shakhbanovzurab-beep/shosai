"""The evaluation's runner over the slot's homes and Valkey (agent step 8).

The runner is the one `shosai agent eval` builds: the slices' real tool specs answered by the
scenarios, the made-up people erased by agent's and core's handlers after each run.
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest_asyncio
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.composition.features import FEATURES
from shosai.core.agent_tools.spec import ToolSpec
from shosai.core.email.account_data import CoreAccountData
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimiter
from shosai.features.agent.application.account_data import AgentAccountData
from shosai.features.agent.application.eval_model import SCRIPTED_ROUTE
from shosai.features.agent.application.eval_runner import EvalRunner, EvalServices
from shosai.features.agent.application.eval_stage import answered_specs
from shosai.features.agent.module import AGENT
from tests.harness.database_access import DatabaseAccess


def slice_specs() -> tuple[ToolSpec[Any, Any], ...]:
    """Every tool a scenario answers: the slices' and the agent's own but core's."""
    return answered_specs(FEATURES)


def eval_services(homes: DatabaseAccess, valkey: Redis) -> EvalServices:
    """What the runner works with over the slot."""
    registry = CollectorRegistry()
    return EvalServices(
        transactions=homes.transactions,
        valkey=valkey,
        effects=EffectLedger(EffectKeyMetrics(registry)),
        limiter=RateLimiter(valkey, KeyValueMetrics(registry)),
        outbox=EventOutbox(EventTypes([*AGENT.events])),
        erasers=(AgentAccountData(homes.transactions, valkey), CoreAccountData(homes.transactions)),
        specs=slice_specs(),
    )


@pytest_asyncio.fixture
async def eval_runner(homes: DatabaseAccess, valkey: Redis) -> AsyncIterator[EvalRunner]:
    """The runner, present in the fleet as an agent worker."""
    runner = EvalRunner(eval_services(homes, valkey), SCRIPTED_ROUTE)
    async with runner.serving():
        yield runner

"""The decisions slice as composition sees it (decisions plan §3.1).

Step 1 published the contract, the domain and the three policies of this plan; step 2 added
the tables and the declaration of what they hold of a person — nothing that outlives its
partition; step 3 the engine bound to `DECISION_LAYER`: the versions in force, Jev through
the provider port with the caller waiting only the policy's deadline, records written in
batches off every path, and the daily check that Jev's endpoint keeps nothing. The agent's
ports and the operator's command come with the next steps.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from functools import partial
from typing import Final

import httpx

from shosai.core.account_data.spec import AccountDataSpec, TableCoverage, Treatment
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.features.decisions.application.asking import Asker
from shosai.features.decisions.application.engine import DecisionEngine
from shosai.features.decisions.application.in_force import PoliciesInForce
from shosai.features.decisions.application.recording import Recorder
from shosai.features.decisions.channels.tasks import PERIODIC_JOBS, zero_retention_check
from shosai.features.decisions.contracts import DECISION_LAYER
from shosai.features.decisions.domain.policies import policies_by_key
from shosai.features.decisions.infrastructure.metrics import DecisionMetrics
from shosai.features.decisions.infrastructure.policy_store import PolicyStore
from shosai.features.decisions.infrastructure.provider_terms import ProviderTerms
from shosai.features.decisions.infrastructure.record_writer import RecordWriter
from shosai.features.decisions.infrastructure.records import (
    DECISION_MODELS,
    DecisionOutcomeRow,
    DecisionRow,
)
from shosai.features.decisions.infrastructure.state_key import state_hash_key
from shosai.features.decisions.settings import DecisionsSettings

# Трассировщик среза: спаны decision.<точка> без состояния и текста.
TRACER_NAME: Final = "shosai.decisions"
# Записи — только идентификаторы, числа и коды без id человека: истекают со своей партицией.
ACCOUNT_DATA: Final = AccountDataSpec(
    "decisions",
    tuple(
        TableCoverage(model.__tablename__, Treatment.EXPIRES)
        for model in (DecisionRow, DecisionOutcomeRow)
    ),
)
PUBLIC_API_TIMEOUT: Final = httpx.Timeout(30.0, connect=5.0)


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """The engine and its writer for this process; on stop, the calls in flight land first."""
    settings = services.settings.features.get(DecisionsSettings)
    metrics = DecisionMetrics(services.registry)
    terms = ProviderTerms(services.valkey, settings.decisions_jev_model, services.registry)
    writer = RecordWriter(services.transactions, metrics)
    recorder = Recorder(
        writer, terms, metrics, partial(datetime.now, UTC), state_hash_key(services.settings.crypto)
    )
    engine = DecisionEngine(
        (
            PoliciesInForce(PolicyStore(services.transactions), policies_by_key()),
            Asker(services.ai, settings.jev_route()),
            recorder,
        ),
        (metrics, services.tracer_provider.get_tracer(TRACER_NAME)),
        max_in_flight=settings.decisions_max_in_flight,
    )
    check = partial(zero_retention_check, terms=terms, model=settings.decisions_jev_model)
    async with httpx.AsyncClient(timeout=PUBLIC_API_TIMEOUT) as client, writer.running():
        try:
            yield FeatureParts(
                task_handlers=(check(client),),
                periodic_jobs=PERIODIC_JOBS,
                provides=(DECISION_LAYER.bind(engine),),
            )
        finally:
            await engine.drain()


DECISIONS = FeatureModule(
    name="decisions",
    build=build,
    models=DECISION_MODELS,
    settings=(DecisionsSettings,),
    account_data=(ACCOUNT_DATA,),
)

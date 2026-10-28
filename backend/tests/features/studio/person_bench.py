"""The person's Studio over HTTP: bearer tokens, agent's skill reader over the slot's homes,
each person's plan as the test sets it, and the catalogue bench for the models."""

import uuid
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from uuid import UUID

import httpx
import pytest_asyncio
from prometheus_client import CollectorRegistry

from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.installed_skills import InstalledSkills
from shosai.features.agent.contracts import SKILL_READER
from shosai.features.agent.infrastructure.person_records import AgentSkillRecord
from shosai.features.billing.contracts import (
    ENTITLEMENTS,
    Audience,
    Capability,
    EntitlementSnapshot,
    EntitlementSource,
    EntitlementsUnavailableError,
    PlanLimits,
)
from shosai.features.identity.contracts import AUTHENTICATOR
from shosai.features.studio.application.person_prompts import PersonPrompts
from shosai.features.studio.application.person_settings import PersonSettings
from shosai.features.studio.channels.http.studio_routes import build_studio_router
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.people_bench import BearerOfTheTest, bearer
from tests.features.studio.catalogue_bench import CatalogueBench, catalogue_bench
from tests.harness.database_access import DatabaseAccess

type Person = tuple[Home, UUID]


@dataclass
class Plans:
    """Each person's plan: frontier models for those listed; unreadable when asked."""

    frontier: set[UUID] = field(default_factory=set)
    unreadable: bool = False

    async def snapshot(self, home: Home, user_id: UUID) -> EntitlementSnapshot:
        """The person's plan as billing would give it."""
        del home
        if self.unreadable:
            raise EntitlementsUnavailableError
        capabilities = frozenset({Capability.FRONTIER_MODELS} if user_id in self.frontier else ())
        return EntitlementSnapshot(
            user_id=user_id, plan_slug="pro", plan_name="Pro", audience=Audience.INDIVIDUAL,
            paid=True, in_grace=False, paid_until=None, limits=PlanLimits(None, None, None),
            capabilities=capabilities, source=EntitlementSource.PERSONAL, workspace_id=None,
            version=1,
        )  # fmt: skip


@dataclass(frozen=True, slots=True)
class PersonBench:
    """The routes, the catalogue underneath and the plans the test sets."""

    http: httpx.AsyncClient
    catalogue: CatalogueBench
    plans: Plans
    homes: DatabaseAccess

    async def install(self, person: Person, name: str, body: str = "Do it well.") -> UUID:
        """A skill the person installed, as agent keeps it."""
        home, user_id = person
        skill_id = uuid.uuid4()
        async with self.homes.transactions.begin(TenancyScope(home, user_id)) as session:
            session.add(
                AgentSkillRecord(
                    id=skill_id, user_id=user_id, source="github", repo=f"acme/{name}",
                    skill_path="", ref="a" * 40, slug=name, body=body,
                )
            )  # fmt: skip
        return skill_id

    async def create(
        self, person: Person, body: Mapping[str, object], key: str | None = None
    ) -> httpx.Response:
        """A create with its key, a new one unless given."""
        headers = bearer(person) | {"Idempotency-Key": key or str(uuid.uuid4())}
        return await self.http.post("/v1/studio/prompts", json=body, headers=headers)


def someone(home: Home = Home.RU) -> Person:
    """A new person of the home."""
    return home, uuid.uuid4()


@pytest_asyncio.fixture
async def person_bench(homes: DatabaseAccess) -> AsyncIterator[PersonBench]:
    """Studio's person routes over the slot's homes."""
    catalogue, plans = catalogue_bench(homes), Plans()
    effects = EffectLedger(EffectKeyMetrics(CollectorRegistry()))
    ports = PortDirectory()
    ports.install(
        [
            AUTHENTICATOR.bind(BearerOfTheTest()),
            SKILL_READER.bind(InstalledSkills()),
            ENTITLEMENTS.bind(plans),
        ]
    )
    services = (
        PersonPrompts(homes.transactions, (effects, ports)),
        PersonSettings(homes.transactions, (catalogue.snapshot, ports)),
    )
    app = build_probe_app(extra=(build_studio_router(services, ports),)).app
    async with client_of(app) as http:
        yield PersonBench(http, catalogue, plans, homes)

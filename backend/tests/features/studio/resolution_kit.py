"""The resolution's bench: a catalogue with defaults, billing's allowance as the test sets it,
agent's skill reader over the slot's homes, and a person's rows written in their home."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from prometheus_client import CollectorRegistry

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.installed_skills import InstalledSkills
from shosai.features.agent.contracts import SKILL_READER
from shosai.features.agent.infrastructure.person_records import AgentSkillRecord
from shosai.features.billing.contracts import TOKEN_ALLOWANCE, ModelTier, TokenDecision, TokenRoute
from shosai.features.studio.application.model_routes import StudioModelRoutes
from shosai.features.studio.application.platform_reader import PlatformPromptReader
from shosai.features.studio.application.prompt_resolver import StudioPromptResolver
from shosai.features.studio.contracts import RoutePerson
from shosai.features.studio.domain.roles import ModelRole, Tier
from shosai.features.studio.infrastructure.person_records import (
    PromptRecord,
    PromptSkillRecord,
    RoleModelRecord,
    RolePromptRecord,
)
from shosai.features.studio.infrastructure.route_metrics import RouteMetrics
from tests.features.studio.catalogue_bench import CatalogueBench, entry, openrouter_list

FLASH, MINI = "google/gemini-3.8-flash", "google/gemini-3.8-mini"
SONNET, SMALL = "anthropic/claude-sonnet-5", "mistral/small-4"


@dataclass
class Allowance:
    """Billing's decision per tier, within the allowance unless the test says otherwise."""

    decisions: dict[ModelTier, TokenDecision] = field(default_factory=dict)
    asked: list[ModelTier] = field(default_factory=list)

    async def decision(self, home: Home, user_id: UUID, tier: ModelTier) -> TokenDecision:
        """The decision of the tier as the test set it."""
        del home, user_id
        self.asked.append(tier)
        return self.decisions.get(tier, TokenDecision(TokenRoute.WITHIN_ALLOWANCE))


@dataclass(frozen=True, slots=True)
class Resolution:
    """The routes and the resolver over one catalogue, with what the test controls."""

    catalogue: CatalogueBench
    routes: StudioModelRoutes
    resolver: StudioPromptResolver
    allowance: Allowance
    registry: CollectorRegistry
    ids: dict[str, str]

    def counted(self, name: str, **labels: str) -> float:
        """A metric's value."""
        return self.registry.get_sample_value(name, labels) or 0.0


async def resolution(catalogue: CatalogueBench) -> Resolution:
    """Four models — a frontier one, a text-only one — and defaults for every role but one."""
    entries = (
        entry(FLASH, image=True, reasoning=True),
        entry(MINI, image=True),
        entry(SONNET, image=True),
        entry(SMALL),
    )
    ids: dict[str, str] = {}
    for model_id in (FLASH, MINI, SONNET, SMALL):
        catalogue.lists(openrouter_list(*entries))
        tier = Tier.FRONTIER if model_id == SONNET else Tier.STANDARD
        model = await catalogue.admin.add(model_id, tier)
        await catalogue.admin.switch(model.id, enabled=True)
        ids[model_id] = model.id
    for role in (
        ModelRole.LEO,
        ModelRole.LIVE_ANSWERS,
        ModelRole.SCREENSHOTS,
        ModelRole.CODE,
        ModelRole.NOTES,
    ):
        await catalogue.admin.set_default(role, ids[FLASH], ids[MINI])
    allowance, registry = Allowance(), CollectorRegistry()
    ports = PortDirectory()
    ports.install([TOKEN_ALLOWANCE.bind(allowance), SKILL_READER.bind(InstalledSkills())])
    metrics = RouteMetrics(registry)
    routes = StudioModelRoutes(catalogue.snapshot, ports, metrics)
    resolver = StudioPromptResolver(PlatformPromptReader(catalogue.snapshot), ports, metrics)
    return Resolution(catalogue, routes, resolver, allowance, registry, ids)


async def settings_row(
    person: RoutePerson,
    role: str,
    model_id: str | None,
    *,
    reasoning: bool = False,
    bench: CatalogueBench,
) -> None:
    """The person's settings of a role, as Studio saves them."""
    async with bench.homes.transactions.begin(TenancyScope(person.home, person.user_id)) as session:
        session.add(
            RoleModelRecord(
                user_id=person.user_id, role=role, model_id=model_id, temperature=Decimal("0.30"),
                max_tokens=2_000, reasoning=reasoning,
            )
        )  # fmt: skip


async def active_prompt(
    bench: CatalogueBench, person: RoutePerson, content: str, skills: Sequence[tuple[str, str]]
) -> list[UUID]:
    """The person's active `code` prompt with installed skills `(name, body)` in order."""
    scope = TenancyScope(person.home, person.user_id)
    prompt_id, skill_ids = uuid.uuid4(), [uuid.uuid4() for _ in skills]
    async with bench.homes.transactions.begin(scope) as session:
        for skill_id, (name, body) in zip(skill_ids, skills, strict=True):
            session.add(
                AgentSkillRecord(
                    id=skill_id, user_id=person.user_id, source="github", repo=f"acme/{name}",
                    skill_path="", ref="a" * 40, slug=name, body=body,
                )
            )  # fmt: skip
        session.add(
            PromptRecord(
                id=prompt_id, user_id=person.user_id, name="Code", role="code", content=content
            )
        )
        await session.flush()
        session.add_all(
            PromptSkillRecord(
                id=uuid.uuid4(),
                user_id=person.user_id,
                prompt_id=prompt_id,
                skill_id=skill_id,
                position=position,
            )
            for position, skill_id in enumerate(skill_ids)
        )
        session.add(RolePromptRecord(user_id=person.user_id, role="code", prompt_id=prompt_id))
    return skill_ids

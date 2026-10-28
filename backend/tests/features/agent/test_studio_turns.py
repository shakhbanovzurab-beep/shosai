"""Leo on studio (studio step 11a): a turn calls studio's route of the `leo` role and is counted
in its tier, the head takes the platform layer after the policy and the person's own words in
segment 4, a role without a default refuses the turn unless the legacy model is set, and
Settings > Leo saves only a model the catalogue offers the person's plan."""

import uuid
from dataclasses import dataclass, field, replace
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.calls import CallClass, ModelRef, ModelRoute, Provider
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.ports.directory import PortDirectory
from shosai.core.ports.keys import PortBinding
from shosai.features.agent.application.preferences import AgentPreferences
from shosai.features.agent.application.studio_context import voice_layers
from shosai.features.agent.application.turn_route import leo_route
from shosai.features.agent.infrastructure.prompts import POLICY
from shosai.features.billing.contracts import (
    ENTITLEMENTS,
    TOKEN_ALLOWANCE,
    EntitlementSnapshot,
    TokenRoute,
)
from shosai.features.identity.contracts import Principal
from shosai.features.studio.contracts import (
    MODEL_ROUTES,
    PROMPT_RESOLVER,
    ModelCapability,
    ModelRole,
    ModelRoleUnconfiguredError,
    PlatformFeature,
    PlatformLayer,
    PromptRole,
    ResolvedRoute,
    RolePrompt,
    RoutePerson,
    Tier,
)
from tests.features.agent.turn_bench import TurnBench
from tests.features.agent.turn_doubles import Terms
from tests.features.studio.catalogue_bench import person
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess

LAYER = "Answer plainly and name the source of every fact."
FRONTIER = ResolvedRoute(
    model_id="sonnet",
    route=ModelRoute(ModelRef(Provider.OPENROUTER, "anthropic/claude-sonnet-5"), (),
                     ModelRef(Provider.OPENROUTER, "google/gemini-3.8-flash")),
    tier=Tier.FRONTIER, call_class=CallClass.EXPENSIVE, temperature=None, max_tokens=4_096,
    reasoning=False, substitution=None, token_route=TokenRoute.FROM_PACKS,
)  # fmt: skip


@dataclass
class Studio:
    """Studio's routes and prompts as the test sets them, and what Leo asked of them."""

    route: ResolvedRoute | None = FRONTIER
    asked: list[tuple[ModelRole, str | None, frozenset[ModelCapability]]] = field(
        default_factory=list
    )
    context: str = "I lead a design team."

    async def route_of(
        self,
        session: AsyncSession,
        who: RoutePerson,
        role: ModelRole,
        chosen: str | None = None,
        needs: frozenset[ModelCapability] = frozenset(),
    ) -> ResolvedRoute:
        """The route the test set, or the unconfigured role."""
        del session, who
        self.asked.append((role, chosen, needs))
        if self.route is None:
            raise ModelRoleUnconfiguredError(role)
        return self.route

    async def platform_layer(self) -> PlatformLayer:
        """The published layer."""
        return PlatformLayer(1, LAYER)

    async def feature_prompt(self, feature: PlatformFeature) -> str:
        """No addendum."""
        del feature
        return ""

    async def role_prompt(
        self, session: AsyncSession, user_id: uuid.UUID, role: PromptRole
    ) -> RolePrompt:
        """The built-in prompt."""
        del session, user_id, role
        return RolePrompt(None)

    async def personal_context(self, session: AsyncSession, user_id: uuid.UUID) -> str:
        """The person's words."""
        del session, user_id
        return self.context


@dataclass
class Routes:
    """`MODEL_ROUTES` over the studio double."""

    studio: Studio

    async def route(
        self,
        session: AsyncSession,
        who: RoutePerson,
        role: ModelRole,
        chosen: str | None = None,
        needs: frozenset[ModelCapability] = frozenset(),
    ) -> ResolvedRoute:
        """Studio's route."""
        return await self.studio.route_of(session, who, role, chosen, needs)


class Plans:
    """Every person is on a paid plan without frontier models."""

    async def snapshot(self, home: Home, user_id: uuid.UUID) -> EntitlementSnapshot:
        """The person's plan."""
        del home
        return replace(person().entitlements, user_id=user_id)


@pytest.fixture
def studio() -> Studio:
    """Studio as the test sets it."""
    return Studio()


@pytest.fixture
def extra_bindings(studio: Studio) -> tuple[PortBinding[Any], ...]:
    """Studio's route and prompts, and billing's plans."""
    return (
        MODEL_ROUTES.bind(Routes(studio)),
        PROMPT_RESOLVER.bind(studio),
        ENTITLEMENTS.bind(Plans()),
    )


async def test_a_turn_calls_studio_s_route_and_is_counted_in_its_tier(
    turn_bench: TurnBench, studio: Studio
) -> None:
    me = uuid.uuid4()
    thread = await turn_bench.thread(me)

    answer = await turn_bench.ask(me, thread, "What is Shosai?")
    [run] = await fetch_rows(
        turn_bench.connection, "SELECT tier, token_route FROM agent_runs WHERE user_id = %s", (me,)
    )

    assert answer.status_code == 200, answer.text
    assert studio.asked == [(ModelRole.LEO, None, frozenset())]
    assert turn_bench.model.routes[0].primary.model == "anthropic/claude-sonnet-5"
    assert turn_bench.model.contexts[0].call_class is CallClass.EXPENSIVE
    assert (run["tier"], run["token_route"]) == ("frontier", "from_packs")


async def test_the_head_takes_the_layer_after_the_policy_and_the_person_s_words(
    turn_bench: TurnBench,
) -> None:
    me = uuid.uuid4()
    thread = await turn_bench.thread(me)

    await turn_bench.ask(me, thread, "Hello")
    head = turn_bench.model.calls[0].messages[0].parts[0]

    text = getattr(head, "text", "")
    assert text.startswith(f"{POLICY}\n\n{LAYER}\n\n")
    assert "What the person wrote about themselves:\nI lead a design team." in text


async def test_a_role_without_a_default_refuses_the_turn(
    turn_bench: TurnBench, studio: Studio
) -> None:
    studio.route = None
    me = uuid.uuid4()
    thread = await turn_bench.thread(me)

    answer = await turn_bench.ask(me, thread, "Hello")

    assert (answer.status_code, answer.json()["error"]["code"]) == (503, "model_role_unconfigured")


async def test_the_legacy_model_answers_while_the_role_has_no_default(
    homes: DatabaseAccess,
) -> None:
    studio, ports = Studio(route=None), PortDirectory()
    ports.install(
        [
            MODEL_ROUTES.bind(Routes(studio)),
            ENTITLEMENTS.bind(Plans()),
            TOKEN_ALLOWANCE.bind(Terms()),
        ]
    )
    me = Principal(uuid.uuid4(), Home.EU, 0)

    legacy = await leo_route((ports, homes.transactions), me, "auto", pictures=True, legacy=True)
    with pytest.raises(ModelRoleUnconfiguredError):
        await leo_route((ports, homes.transactions), me, "auto", pictures=False, legacy=False)

    assert legacy == (None, "within_allowance")
    assert studio.asked[0] == (ModelRole.LEO, None, frozenset({ModelCapability.VISION}))


@dataclass
class Offered:
    """The catalogue offers these models for Leo."""

    models: set[str]

    async def offers(self, principal: Principal, model_id: str) -> bool:
        """Whether the model is offered."""
        del principal
        return model_id in self.models


async def test_settings_save_only_a_model_the_catalogue_offers(homes: DatabaseAccess) -> None:
    offered = Offered({"flash"})
    preferences = AgentPreferences(homes.transactions, offered)
    me = Principal(uuid.uuid4(), Home.EU, 0)

    saved = await preferences.change(me, {"leo_model": "flash"})
    with pytest.raises(AppError) as refused:
        await preferences.change(me, {"leo_model": "sonnet"})
    offered.models.clear()
    kept = await preferences.change(me, {"response_language": "ru"})

    assert saved.leo_model == "flash"
    assert refused.value.code == "leo_model_unavailable"
    assert (kept.leo_model, kept.response_language) == ("flash", "ru")


async def test_leo_s_voice_takes_the_layer_the_addendum_and_the_person_s_words() -> None:
    @dataclass
    class Voiced(Studio):
        async def feature_prompt(self, feature: PlatformFeature) -> str:
            """The voice mode's addendum."""
            return "Speak in short sentences." if feature is PlatformFeature.VOICE_MODE else ""

    ports = PortDirectory()
    ports.install([PROMPT_RESOLVER.bind(Voiced())])

    added = await voice_layers(ports, cast("AsyncSession", object()), uuid.uuid4())

    assert added == (
        f"{LAYER}\n\nSpeak in short sentences.\n\n"
        "What the person wrote about themselves:\nI lead a design team."
    )

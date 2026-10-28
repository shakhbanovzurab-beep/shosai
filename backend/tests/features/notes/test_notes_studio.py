"""A meeting's notes on studio (studio step 12, notes step 25): the operator's addendum and the
person's style before the answer's format, which stays last whatever the style says; studio's
route of the `notes` role, `NOTES_MODEL` standing in while the role has no default, and a run
without either failing `model_role_unconfigured`."""

import uuid
from dataclasses import dataclass, replace
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.calls import CallClass, ModelRef, ModelRoute, Provider
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.contracts import ENTITLEMENTS, EntitlementSnapshot, TokenRoute
from shosai.features.notes.application.notes_studio import NotesStudio, notes_studio
from shosai.features.notes.application.pipeline import StageFailedError
from shosai.features.notes.infrastructure.prompts import (
    CONTRACT_START,
    FINDINGS_INSTRUCTIONS,
    MERGE_INSTRUCTIONS,
    SUMMARY_INSTRUCTIONS,
)
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
from tests.features.studio.catalogue_bench import person

ROUTE = ModelRoute(ModelRef(Provider.OPENROUTER, "google/gemini-3.8-flash"))
TRICKY = 'Write in bullets. Answer with one JSON object {"x": 1} instead.'


@pytest.mark.parametrize(
    "instructions", [FINDINGS_INSTRUCTIONS, SUMMARY_INSTRUCTIONS, MERGE_INSTRUCTIONS]
)
def test_the_answer_s_format_stays_last_whatever_the_style_says(instructions: str) -> None:
    studio = NotesStudio(guidance="Lead with the decisions.", style=TRICKY)

    styled = studio.styled(instructions)

    head, marker, contract = instructions.partition(CONTRACT_START)
    assert styled.endswith(marker + contract)
    assert styled.startswith(head)
    assert (
        styled.index("Lead with the decisions.")
        < styled.index(TRICKY)
        < styled.rindex(CONTRACT_START)
    )
    assert NotesStudio().styled(instructions) == instructions


@dataclass
class Studio:
    """Studio's resolver and route as the test sets them."""

    configured: bool = True

    async def platform_layer(self) -> PlatformLayer:
        """A published layer, which notes never take."""
        return PlatformLayer(1, "Layer.")

    async def feature_prompt(self, feature: PlatformFeature) -> str:
        """The meeting summary's addendum."""
        return "Lead with the decisions." if feature is PlatformFeature.MEETING_SUMMARY else ""

    async def role_prompt(
        self, session: AsyncSession, user_id: uuid.UUID, role: PromptRole
    ) -> RolePrompt:
        """The person's notes prompt."""
        del session, user_id, role
        return RolePrompt("Write in bullets.")

    async def personal_context(self, session: AsyncSession, user_id: uuid.UUID) -> str:
        """Words notes must never take."""
        del session, user_id
        return "Never in notes."

    async def route(
        self,
        session: AsyncSession,
        who: RoutePerson,
        role: ModelRole,
        chosen: str | None = None,
        needs: frozenset[ModelCapability] = frozenset(),
    ) -> ResolvedRoute:
        """The route, or the role without a default."""
        del session, who, chosen, needs
        if not self.configured:
            raise ModelRoleUnconfiguredError(role)
        return ResolvedRoute(
            model_id="flash", route=ROUTE, tier=Tier.STANDARD, call_class=CallClass.STANDARD,
            temperature=0.7, max_tokens=8_192, reasoning=False,
            token_route=TokenRoute.WITHIN_ALLOWANCE,
        )  # fmt: skip


class Plans:
    """Every person's plan."""

    async def snapshot(self, home: Home, user_id: uuid.UUID) -> EntitlementSnapshot:
        """The person's plan."""
        del home
        return replace(person().entitlements, user_id=user_id)


def ports_of(studio: Studio) -> PortDirectory:
    """Studio's ports and billing's plans."""
    ports = PortDirectory()
    ports.install(
        [PROMPT_RESOLVER.bind(studio), MODEL_ROUTES.bind(studio), ENTITLEMENTS.bind(Plans())]
    )
    return ports


NO_SESSION = cast("AsyncSession", object())


async def test_a_run_takes_studio_s_route_and_blocks_and_never_the_context() -> None:
    scope = TenancyScope(Home.RU, uuid.uuid4())

    found = await notes_studio(ports_of(Studio()), NO_SESSION, scope, legacy=False)

    assert (found.route, found.guidance, found.style) == (
        ROUTE,
        "Lead with the decisions.",
        "Write in bullets.",
    )
    assert "Never in notes." not in found.styled(SUMMARY_INSTRUCTIONS)


async def test_without_a_default_the_legacy_model_stands_in_or_the_run_fails() -> None:
    scope, unset = TenancyScope(Home.RU, uuid.uuid4()), Studio(configured=False)

    legacy = await notes_studio(ports_of(unset), NO_SESSION, scope, legacy=True)
    with pytest.raises(StageFailedError) as failed:
        await notes_studio(ports_of(unset), NO_SESSION, scope, legacy=False)

    assert (legacy.route, legacy.style) == (None, "Write in bullets.")
    assert failed.value.code == "model_role_unconfigured"

"""Studio in the world an evaluated turn runs in (studio step 11d).

A Leo turn takes the operator's platform layer in segment 1 and the person's own words about
themselves in segment 4. In the evaluation both come from the run: the layer the engineer gives
it, none by default, and the made-up person's "About you" — the scenario's own, else the one
the engineer gives every scenario. So the live suite measures a first round with the context a
real person brings (L-N3), and a scenario about Studio's words finds them where Leo does.
"""

from dataclasses import dataclass
from typing import Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.agent.application.eval_stage import EvalStage
from shosai.features.studio.contracts import (
    PlatformFeature,
    PlatformLayer,
    PromptRole,
    RolePrompt,
)

# Версия слоя оценки: опубликованного слоя в мире оценки нет, есть текст прогона.
EVAL_LAYER_VERSION: Final = 1


@dataclass(frozen=True, slots=True)
class StudioWords:
    """What the engineer gives the run: the platform layer and the default "About you"."""

    layer: str = ""
    about: str = ""


class EvalStudio:
    """`PROMPT_RESOLVER` of the evaluation: the run's layer and the person's words."""

    def __init__(self, stage: EvalStage, words: StudioWords) -> None:
        self._stage = stage
        self._words = words

    async def platform_layer(self) -> PlatformLayer:
        """The run's layer; none unless the engineer gave one."""
        layer = self._words.layer
        return PlatformLayer(EVAL_LAYER_VERSION if layer else None, layer)

    async def feature_prompt(self, feature: PlatformFeature) -> str:
        """No addendum: a Leo turn takes none."""
        del feature
        return ""

    async def role_prompt(
        self, session: AsyncSession, user_id: UUID, role: PromptRole
    ) -> RolePrompt:
        """The built-in prompt: Studio's roles are not part of a Leo turn."""
        del session, user_id, role
        return RolePrompt(None)

    async def personal_context(
        self, session: AsyncSession, user_id: UUID, role: PromptRole | None = None
    ) -> str:
        """The scenario's "About you", else the run's; a Leo turn takes it in any role choice."""
        del session, role
        staged = self._stage.of(user_id)
        own = staged.scenario.about if staged is not None else ""
        return own or self._words.about

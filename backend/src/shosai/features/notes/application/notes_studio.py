"""What studio gives a meeting's notes (studio step 12, notes step 25, studio plan §3.4).

The model is studio's route of the `notes` role for the person the run works for — the owner
of a live run, the person who asked for a rewrite; studio's rows admit only their own. The
operator's `meeting_summary` addendum and the person's `notes` prompt, as a style block, go
into the findings' and the write-up's instructions before the answer's format, which notes
keep and place last; notes take no personal context (ST-D2), since colleagues read them.
Until the `notes` role has a default, the runs keep `NOTES_MODEL` (expand, then contract);
without it a run fails `model_role_unconfigured`.
"""

from dataclasses import dataclass
from typing import Final

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.calls import CallClass, ModelRoute
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.contracts import ENTITLEMENTS
from shosai.features.notes.application.pipeline import StageFailedError
from shosai.features.notes.infrastructure.prompts import CONTRACT_START, GUIDANCE_BLOCK, STYLE_BLOCK
from shosai.features.studio.contracts import (
    MODEL_ROUTES,
    PROMPT_RESOLVER,
    ModelRole,
    ModelRoleUnconfiguredError,
    PlatformFeature,
    PromptRole,
    RoutePerson,
)

MODEL_ROLE_UNCONFIGURED: Final = "model_role_unconfigured"
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class NotesStudio:
    """Studio's route of the run — none is `NOTES_MODEL` — and the two blocks of its prompts."""

    route: ModelRoute | None = None
    call_class: CallClass = CallClass.STANDARD
    guidance: str = ""
    style: str = ""

    def styled(self, instructions: str) -> str:
        """The instructions with studio's blocks before the answer's format."""
        blocks = [
            *([GUIDANCE_BLOCK.format(text=self.guidance)] if self.guidance else []),
            *([STYLE_BLOCK.format(text=self.style)] if self.style else []),
        ]
        if not blocks:
            return instructions
        head, marker, contract = instructions.partition(CONTRACT_START)
        return "\n\n".join([head, *blocks]) + marker + contract


async def notes_studio(
    ports: PortDirectory, session: AsyncSession, scope: TenancyScope, *, legacy: bool
) -> NotesStudio:
    """Studio's part of the run, read in its transaction; empty without studio or a person."""
    resolvers, routes = ports.all(PROMPT_RESOLVER), ports.all(MODEL_ROUTES)
    user_id = scope.user_id
    if user_id is None or not resolvers or not routes:
        return NotesStudio()
    resolver = resolvers[0]
    guidance = await resolver.feature_prompt(PlatformFeature.MEETING_SUMMARY)
    style = (await resolver.role_prompt(session, user_id, PromptRole.NOTES)).body or ""
    plan = await ports.get(ENTITLEMENTS).snapshot(scope.home, user_id)
    try:
        resolved = await routes[0].route(
            session, RoutePerson(scope.home, user_id, plan), ModelRole.NOTES
        )
    except ModelRoleUnconfiguredError as error:
        if not legacy:
            raise StageFailedError(MODEL_ROLE_UNCONFIGURED) from error
        log.warning("Заметки на NOTES_MODEL: у роли notes нет умолчания в каталоге")
        return NotesStudio(guidance=guidance, style=style)
    return NotesStudio(resolved.route, resolved.call_class, guidance, style)

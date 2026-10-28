"""How hard a turn's model reasons, judged beside the rule (decisions' `turn.effort`; agent step
21, the owner's choice of 2026-10-27 — ChatGPT's "Auto").

The rule is the standard tier's effort (`AGENT_STANDARD_REASONING`): a greeting or a one-step
request starts at once. A bound judge reads the person's question, the start of the last
answer, the page's section and how many files came with it — read in one statement of the
run's transaction — and runs while the context is read; the first model request waits for it
at most `EFFORT_WAIT`. Only a sure "deep" raises the turn to `DEEP_EFFORT`; a late, unsure or
absent answer keeps the rule's. A turn the person asked to think longer already reasons at
its highest effort and is never asked about, nor is an operator's turn.
"""

import asyncio
from collections.abc import Sequence
from datetime import timedelta
from typing import Final

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.requests import ReasoningEffort
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.route_ranking import PREVIOUS_CHARS, turn_texts
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.contracts.effort import TURN_EFFORT_JUDGE, EffortJudge, EffortRequest
from shosai.features.agent.domain.operator import is_operator

# Политика отвечает за 450 мс; ход ждёт её не дольше, чем читается контекст.
EFFORT_WAIT: Final = timedelta(milliseconds=500)
ONE_MS: Final = timedelta(milliseconds=1)
# Вопросу, которому нужен вдумчивый разбор: глубже правила, но не «Думать дольше».
DEEP_EFFORT: Final = ReasoningEffort.MEDIUM
log = structlog.stdlib.get_logger(__name__)

type Judged = asyncio.Task[bool | None]


class EffortJudging:
    """Asks the bound judge of a turn's effort and waits for it within the turn's budget."""

    def __init__(self, ports: PortDirectory | None) -> None:
        self._ports = ports

    async def ask(self, session: AsyncSession, payload: TurnPayload, section: str) -> Judged | None:
        """Start the judge on the turn's question; None when there is nobody to ask."""
        judges = self._judges()
        if not judges or payload.think_longer or is_operator(payload.user_id):
            return None
        question, previous, turn = await turn_texts(session, payload)
        request = EffortRequest(
            question=question, previous=previous[:PREVIOUS_CHARS], section=section,
            files=len(payload.attachments), turn=turn, language=payload.language,
            scope=payload.scope(), cross_border_consent=payload.cross_border_consent,
            run_id=payload.run_id,
        )  # fmt: skip
        return asyncio.create_task(judges[0].deep(request))

    @staticmethod
    async def settle(judged: Judged | None) -> ReasoningEffort | None:
        """The raised effort when the judge surely found it needed, waited for at most
        `EFFORT_WAIT`; None keeps the rule's."""
        if judged is None:
            return None
        try:
            async with asyncio.timeout(EFFORT_WAIT.total_seconds()):
                deep = await judged
        except TimeoutError:
            log.warning("Судья усилия не успел: усилие правила", wait_ms=EFFORT_WAIT // ONE_MS)
            return None
        return DEEP_EFFORT if deep else None

    @staticmethod
    def drop(judged: Judged | None) -> None:
        """Stop waiting for a judge the run no longer needs."""
        if judged is not None:
            judged.cancel()

    def _judges(self) -> Sequence[EffortJudge]:
        return () if self._ports is None else self._ports.all(TURN_EFFORT_JUDGE)

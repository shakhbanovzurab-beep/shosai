"""Pieces of untrusted text judged while a run goes on (decisions' `content.injection`, DL-D5).

Every piece that enters a run under an untrusted label — a tool's result or page, the page's
subject, the person's attachments — is put to a bound judge the moment it is wrapped, and the
round goes on without it. The judgements are awaited only before a write's card and at the
run's end, each pending one for at most `JUDGEMENT_WAIT`; a positive one makes the run
suspicious, which the card states. The person's own words carry no label and never come here.
"""

import asyncio
from datetime import timedelta
from typing import Final

import structlog

from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.contracts import INJECTION_JUDGE, InjectionJudge, InjectionPiece
from shosai.features.agent.domain.wrapper import Label

# Дольше политики (300 мс) не ждём ни при каком судье: карточка и конец хода важнее.
JUDGEMENT_WAIT: Final = timedelta(milliseconds=400)
# Кусок контекста, а не результат инструмента.
CONTEXT_TOOL: Final = "context"
log = structlog.stdlib.get_logger(__name__)


class InjectionWatch:
    """One run's pending judgements."""

    def __init__(self, judge: InjectionJudge, payload: TurnPayload) -> None:
        self._judge = judge
        self._payload = payload
        self._parts = 0
        self._pending: list[asyncio.Task[bool | None]] = []

    def start(self, label: Label, text: str, tool: str) -> None:
        """Put a piece to the judge; the run does not wait for it here."""
        payload = self._payload
        self._parts += 1
        piece = InjectionPiece(
            label=label.text, tool=tool, text=text, part=self._parts,
            language=payload.language, scope=payload.scope(),
            cross_border_consent=payload.cross_border_consent, run_id=payload.run_id,
        )  # fmt: skip
        self._pending.append(asyncio.create_task(self._judge.judge(piece)))

    async def settle(self) -> bool:
        """Whether a judgement found instructions, the pending ones waited for at most
        `JUDGEMENT_WAIT`; those still out are let go and leave the run as it is."""
        pending, self._pending = self._pending, []
        if not pending:
            return False
        done, late = await asyncio.wait(pending, timeout=JUDGEMENT_WAIT.total_seconds())
        for task in late:
            task.cancel()
        if late:
            log.warning("Судья содержимого не успел", late=len(late), pieces=len(pending))
        found = False
        for task in done:
            error = task.exception()
            if error is not None:
                log.warning("Судья содержимого упал", error_type=type(error).__name__)
            elif task.result() is True:
                found = True
        return found


def injection_watch(ports: PortDirectory | None, payload: TurnPayload) -> InjectionWatch | None:
    """The run's watch over the bound judge; None when no judge is bound."""
    judges = () if ports is None else ports.all(INJECTION_JUDGE)
    return InjectionWatch(judges[0], payload) if judges else None

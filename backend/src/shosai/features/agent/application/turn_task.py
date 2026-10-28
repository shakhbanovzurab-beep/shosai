"""A turn as a task of the `agent` queue (ADR 0068 AG-D12) and its side of the stream.

The API admits a turn, commits its question and its run, writes `run.started` as the log's
first event and sends this task; an agent worker drives the run from there. A regenerated or
edited turn answers the thread's last question again; the page and its subject come along.
The task is never retried by the queue: a run whose worker was lost is swept as
`process_lost`, and the person's "Retry" asks again. Its deadline outlives the turn's own
180 s, so the run always ends itself. The payload carries what the admission decided —
consent, the answer's language and length, the token route, the switches left on — so the
worker reads only the conversation.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Final, Protocol
from uuid import UUID

from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.agent.application.surface_digest import SubjectKind
from shosai.features.agent.application.turn_route import TurnRoute
from shosai.features.agent.domain.preferences import ResponseLength
from shosai.features.agent.domain.stream import EventData, EventKind, StreamEvent, StreamLedger
from shosai.features.agent.domain.threads import TurnKind
from shosai.features.agent.infrastructure.run_log import RunLog


class TurnPayload(HomeTaskPayload):
    """One admitted turn: its run, its thread, its question and answer, and its terms."""

    run_id: UUID
    thread_id: UUID
    started_at: datetime
    question_id: UUID
    reply_id: UUID
    language: str
    length: ResponseLength
    cross_border_consent: bool
    token_route: str
    # Новые поля необязательны: воркер прежнего образа читает полезную нагрузку нового API.
    kind: TurnKind = TurnKind.NEW
    path: str | None = None
    subject_kind: SubjectKind | None = None
    subject_id: UUID | None = None
    # Включённые переключатели Leo (`ToolSpec.switch`): пусто — инструменты за ними не предлагаются.
    switches_on: tuple[str, ...] = ()
    # Загрузки нового вопроса: приём хода берёт их у files и называет на вопросе.
    attachments: tuple[UUID, ...] = ()
    # «Думать дольше»: модель ответа рассуждает в полную силу, медленнее и дороже.
    think_longer: bool = False
    # Маршрут studio для роли leo (шаг 11 studio); нет — AGENT_STANDARD_MODEL, как прежде.
    route: TurnRoute | None = None


RUN_TURN: Final = TaskDeclaration(
    name="agent.run_turn",
    queue=TaskQueue.AGENT,
    payload=TurnPayload,
    deadline=timedelta(seconds=200),
    retry=NO_RETRY,
)


def started_event(payload: TurnPayload) -> StreamEvent:
    """The log's first event, written by the API before the task is sent."""
    _, event = StreamLedger().emit(
        EventKind.RUN_STARTED,
        {
            "run_id": str(payload.run_id),
            "thread_id": str(payload.thread_id),
            "message_id": str(payload.question_id),
            "reply_id": str(payload.reply_id),
        },
    )
    return event


class Emitter(Protocol):
    """Where a run's events go: its log for a text turn, the socket for a voice exchange."""

    async def emit(self, kind: EventKind, data: EventData) -> StreamEvent:
        """Send one event and return it with its number."""
        ...


class RunEmitter:
    """The worker's side of a run's stream: the next numbers after `run.started`.

    Parallel tool calls emit at once; events go to the log one at a time, in their numbers'
    order, since the log takes each number only after the one before.
    """

    def __init__(self, run_log: RunLog, run_id: UUID, after: int = 1) -> None:
        self._log = run_log
        self._run_id = run_id
        # Номер последнего события журнала: `run.started` для нового хода, больше — для решения.
        self._ledger = StreamLedger(seq=after)
        self._order = asyncio.Lock()

    async def emit(self, kind: EventKind, data: EventData) -> StreamEvent:
        """Append one event to the run's log."""
        async with self._order:
            self._ledger, event = self._ledger.emit(kind, data)
            await self._log.append(self._run_id, (event,))
        return event

    async def text(self, text: str) -> None:
        """Append a piece of the answer."""
        await self.emit(EventKind.TEXT_DELTA, {"text": text})

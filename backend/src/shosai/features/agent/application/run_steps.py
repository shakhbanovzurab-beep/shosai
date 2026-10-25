"""The nodes' work for one run: the context and its tools, each model round, each tool round,
and the conversation again after a card's decision.

The context and the run's toolsets are read in one transaction as the person; wrapped text in
the context — a page's subject someone else wrote — taints the run before the first round.
The conversation lives here, never in the frame's state: a resumed run reads it back from the
database — the context, its own rounds before the card and the server note on what became of
the action — and goes on with its steps, sources, taint and toolsets as they were. Each round
asks the model through the provider port under its own effect key, with the tools its number
allows (Leo §8.3): from the fifth the model is asked to conclude, and the tenth offers no tools
and tells it so, so the loop always ends; a call the model makes anyway in a round without
tools is dropped. The model's time and the tools' time are measured apart, since neither is
the platform's own.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import timedelta
from uuid import UUID

from shosai.core.agent_tools.provenance import Provenance
from shosai.core.ai.calls import CallClass, CallContext, CallOrigin, ModelRoute
from shosai.core.ai.requests import ChatMessage, ChatRequest, Role
from shosai.features.agent.application.model_stream import AnswerBuffer, stream_answer
from shosai.features.agent.application.run_context import text_message
from shosai.features.agent.application.run_earlier import earlier_work
from shosai.features.agent.application.run_engine_parts import EngineParts
from shosai.features.agent.application.run_telemetry import TurnTimes
from shosai.features.agent.application.run_work import RunWork
from shosai.features.agent.application.tool_offer import TurnOffer
from shosai.features.agent.application.tool_round import ToolRound
from shosai.features.agent.application.turn_task import RunEmitter, TurnPayload
from shosai.features.agent.domain.budgets import Segment, round_policy
from shosai.features.agent.domain.runs import TURN_DEADLINE
from shosai.features.agent.domain.wrapper import Label
from shosai.features.agent.infrastructure.prompts import CONCLUDE, LAST_ROUND
from shosai.features.agent.infrastructure.turn_graph import ModelAnswer


@dataclass(frozen=True, slots=True)
class RunState:
    """One run as its steps see it: the turn, its model, its times, its text and its work."""

    payload: TurnPayload
    # None — модель не задана: движок кончает такой ход, не доходя до шагов.
    route: ModelRoute | None
    times: TurnTimes
    buffer: AnswerBuffer
    work: RunWork
    emitter: RunEmitter


class RunSteps:
    """The frame's steps of one run."""

    def __init__(
        self,
        parts: EngineParts,
        run: RunState,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._parts = parts
        self._run = run
        self._monotonic = monotonic
        self._request: ChatRequest | None = None

    async def context(self) -> None:
        """The policy, the recent conversation and the question; the run's toolsets."""
        payload, sizes = self._run.payload, self._run.times.sizes
        labels: list[Provenance] = []
        with self._parts.telemetry.context():
            async with self._parts.transactions.begin(payload.scope(), read_only=True) as session:
                request = await self._parts.context.request(session, payload, sizes, labels)
                offer = await self._parts.routing.offer(session, payload)
        self._begin(request, offer, labels)

    async def resume(self, action_id: UUID) -> None:
        """After the card's decision: the context again, the run's rounds before the card and
        the note on what became of the action, with the run's work as it was."""
        payload, sizes, work = self._run.payload, self._run.times.sizes, self._run.work
        labels: list[Provenance] = []
        with self._parts.telemetry.context():
            async with self._parts.transactions.begin(payload.scope(), read_only=True) as session:
                request = await self._parts.context.request(session, payload, sizes, labels)
                offer = await self._parts.routing.offer(session, payload)
                earlier = await earlier_work(session, payload, action_id)
        offer.restore(earlier.routing)
        work.resume_from(earlier)
        if any(source.org_id is not None for source in earlier.sources):
            await self._parts.tools.sources.admit(work, payload, ())
        self._run.buffer.restore(earlier.text)
        self._begin(request, offer, labels, earlier.messages)

    def _begin(
        self,
        request: ChatRequest,
        offer: TurnOffer,
        labels: list[Provenance],
        earlier: tuple[ChatMessage, ...] = (),
    ) -> None:
        work = self._run.work
        work.offer = offer
        for provenance in labels:
            work.read_wrapped(Label.of(provenance))
        self._run.times.sizes[Segment.TOOLS] = offer.tokens()
        self._request = replace(request, messages=(*request.messages, *earlier))

    async def model(self) -> ModelAnswer:
        """One round's answer through the provider port, streamed as it is written."""
        payload, work, route = self._run.payload, self._run.work, self._run.route
        request = self._current()
        if route is None:
            message = "раунд модели без маршрута"
            raise RuntimeError(message)
        number = work.round_number + 1
        policy = round_policy(number)
        tools = work.offer.schemas() if policy.tools and work.offer is not None else ()
        note = LAST_ROUND if not policy.tools else CONCLUDE if policy.conclude else None
        if note is not None:
            request = replace(request, messages=(*request.messages, text_message(Role.USER, note)))
        context = CallContext(
            effect_key=f"agent.turn:{payload.run_id}:{number}",
            feature="agent.turn",
            call_class=CallClass.STANDARD,
            origin=CallOrigin.INTERACTIVE,
            scope=payload.scope(),
            cross_border_consent=payload.cross_border_consent,
            deadline=TURN_DEADLINE,
        )
        self._run.buffer.begin_round()
        began = self._monotonic()
        deltas = self._parts.ai.stream_chat(context, route, replace(request, tools=tools))
        try:
            answer = await stream_answer(deltas, self._run.buffer, self._parts.pace)
        finally:
            self._run.times.model += timedelta(seconds=self._monotonic() - began)
        if not tools and answer.tool_calls:
            answer = replace(answer, tool_calls=())
        work.answers.append(answer)
        return answer

    async def tools(self) -> UUID | None:
        """Run the last answer's calls into the conversation; the action a write proposed."""
        run, request = self._run, self._current()
        began = self._monotonic()
        try:
            round_messages = await ToolRound(
                self._parts.tools, (run.payload, run.work, run.emitter)
            ).run(run.work.round_number, run.work.answers[-1])
        finally:
            run.times.tools += timedelta(seconds=self._monotonic() - began)
        self._request = replace(request, messages=(*request.messages, *round_messages))
        return run.work.proposed

    def answer(self) -> ModelAnswer | None:
        """The model's last answer in this run."""
        answers = self._run.work.answers
        return answers[-1] if answers else None

    def _current(self) -> ChatRequest:
        if self._request is None:
            message = "раунд хода до его контекста"
            raise RuntimeError(message)
        return self._request

"""The nodes' work for one run: the context and its tools, each model round, each tool round.

The context and the run's toolsets are read in one transaction as the person; wrapped text in
the context — a page's subject someone else wrote — taints the run before the first round.
Each round asks the model through the provider port under its own effect key, with the tools
its number allows (Leo §8.3): from the fifth the model is asked to conclude, and the tenth
offers no tools and tells it so, so the loop always ends; a call the model makes anyway in a
round without tools is dropped. The model's time and the tools' time are measured apart,
since neither is the platform's own.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import timedelta

from shosai.core.agent_tools.provenance import Provenance
from shosai.core.ai.calls import CallClass, CallContext, CallOrigin, ModelRoute
from shosai.core.ai.requests import ChatRequest, Role
from shosai.features.agent.application.model_stream import AnswerBuffer, stream_answer
from shosai.features.agent.application.run_context import text_message
from shosai.features.agent.application.run_engine_parts import EngineParts
from shosai.features.agent.application.run_telemetry import TurnTimes
from shosai.features.agent.application.run_work import RunWork
from shosai.features.agent.application.tool_round import ToolRound
from shosai.features.agent.application.turn_task import RunEmitter, TurnPayload
from shosai.features.agent.domain.budgets import Segment, round_policy
from shosai.features.agent.domain.runs import TURN_DEADLINE
from shosai.features.agent.domain.wrapper import Label, taint_after
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

    async def context(self) -> ChatRequest:
        """The policy, the recent conversation and the question; the run's toolsets."""
        payload, sizes = self._run.payload, self._run.times.sizes
        labels: list[Provenance] = []
        with self._parts.telemetry.context():
            async with self._parts.transactions.begin(payload.scope(), read_only=True) as session:
                request = await self._parts.context.request(session, payload, sizes, labels)
                offer = await self._parts.routing.offer(session, payload)
        work = self._run.work
        work.offer = offer
        for provenance in labels:
            work.taint = taint_after(work.taint, Label.of(provenance))
        sizes[Segment.TOOLS] = offer.tokens()
        return request

    async def model(self, request: ChatRequest) -> ModelAnswer:
        """One round's answer through the provider port, streamed as it is written."""
        payload, work, route = self._run.payload, self._run.work, self._run.route
        if route is None:
            message = "раунд модели без маршрута"
            raise RuntimeError(message)
        number = len(work.answers) + 1
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

    async def tools(self, request: ChatRequest, answer: ModelAnswer) -> ChatRequest:
        """The conversation with the round's calls and what they returned."""
        run = self._run
        began = self._monotonic()
        try:
            round_messages = await ToolRound(
                self._parts.tools, (run.payload, run.work, run.emitter)
            ).run(len(run.work.answers), answer)
        finally:
            run.times.tools += timedelta(seconds=self._monotonic() - began)
        return replace(request, messages=(*request.messages, *round_messages))

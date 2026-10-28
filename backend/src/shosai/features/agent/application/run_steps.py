"""The nodes' work for one run: the context and its tools, each model round, each tool round,
and the conversation again after a card's decision.

The question's attachments are read first — each a step of the turn; images go to the model
beside the question. The context and the run's toolsets are read in one transaction as the
person; wrapped text in the context — a page's subject someone else wrote, an attachment's
text — taints the run before the first round.
The conversation lives here, never in the frame's state: a resumed run reads it back from the
database — the context, its own rounds before the card and the server note on what became of
the action, with an approved call's result as that call's answer — and goes on with its
steps, sources, taint and toolsets as they were. Each round
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
from shosai.core.ai.requests import ChatMessage, ChatRequest, ImagePart, ReasoningEffort, Role
from shosai.features.agent.application.effort_judging import EffortJudging
from shosai.features.agent.application.egress_answers import EgressAnswers, kept_call
from shosai.features.agent.application.model_stream import AnswerBuffer, stream_answer
from shosai.features.agent.application.page_toolsets import page_section
from shosai.features.agent.application.run_context import PreparedContext, text_message
from shosai.features.agent.application.run_earlier import earlier_work
from shosai.features.agent.application.run_engine_parts import EngineParts
from shosai.features.agent.application.run_telemetry import TurnTimes
from shosai.features.agent.application.run_work import RunWork
from shosai.features.agent.application.tool_offer import TurnOffer
from shosai.features.agent.application.tool_read_back import ResultReader
from shosai.features.agent.application.tool_round import ToolRound
from shosai.features.agent.application.turn_task import RunEmitter, TurnPayload
from shosai.features.agent.domain.budgets import Segment, estimate_tokens, round_policy
from shosai.features.agent.domain.operator import payer_of
from shosai.features.agent.domain.runs import TURN_DEADLINE
from shosai.features.agent.domain.wrapper import Label, unwrapped
from shosai.features.agent.infrastructure.prompts import CONCLUDE, LAST_ROUND
from shosai.features.agent.infrastructure.turn_graph import ModelAnswer


def with_images(request: ChatRequest, images: tuple[ImagePart, ...]) -> ChatRequest:
    """The request with the question's images beside its text, in its last message."""
    if not images:
        return request
    *before, question = request.messages
    asked = replace(question, parts=(*question.parts, *images))
    return replace(request, messages=(*before, asked))


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
        """The question's attachments, then the policy, the recent conversation and the
        question with its images; the run's toolsets, ranked by a bound router while the
        context is read when the rule leaves one out, and its reasoning raised when a bound
        judge surely finds the question needs it."""
        payload, sizes, run = self._run.payload, self._run.times.sizes, self._run
        images = await self._parts.attachments.read(payload, run.work, run.emitter)
        labels: list[tuple[Provenance, str]] = []
        routing, effort = self._parts.routing, EffortJudging(self._parts.ports)
        with self._parts.telemetry.context():
            async with self._parts.transactions.begin(payload.scope(), read_only=True) as session:
                offer = await routing.offer(session, payload)
                asked = await routing.ask(session, payload, offer)
                judged = await effort.ask(session, payload, page_section(payload))
                try:
                    prepared = await self._parts.context.prepare(
                        session, payload, sizes, labels, recall=True
                    )
                except BaseException:
                    routing.drop(asked)
                    effort.drop(judged)
                    raise
            await routing.settle(offer, asked)
            raised = await effort.settle(judged)
            request = await self._recalled(prepared, sizes, labels)
        if raised is not None:
            request = replace(request, reasoning=raised)
        self._begin(with_images(request, images), offer, labels)

    async def _recalled(
        self,
        prepared: PreparedContext,
        sizes: dict[Segment, int],
        labels: list[tuple[Provenance, str]],
    ) -> ChatRequest:
        """The request with what memory recalled for the question, awaited after the
        transaction; nothing in time is nothing."""
        pending = () if prepared.recalling is None else (prepared.recalling,)
        recalled = await self._parts.context.memory.recalled(pending)
        labels.extend(recalled.tainting)
        sizes[Segment.VOLATILE] = sizes.get(Segment.VOLATILE, 0) + estimate_tokens(recalled.text)
        return self._parts.context.build(prepared, recalled)

    async def resume(self, action_id: UUID) -> None:
        """After the card's decision: the context again, the run's rounds before the card and
        the note on what became of the action, with the run's work as it was."""
        payload, sizes, work = self._run.payload, self._run.times.sizes, self._run.work
        labels: list[tuple[Provenance, str]] = []
        with self._parts.telemetry.context():
            async with self._parts.transactions.begin(payload.scope(), read_only=True) as session:
                request = await self._parts.context.request(session, payload, sizes, labels)
                offer = await self._parts.routing.offer(session, payload)
                earlier = await earlier_work(session, payload, action_id)
                kept = await kept_call(session, payload, action_id)
        offer.restore(earlier.routing)
        work.resume_from(earlier)
        if any(source.org_id is not None for source in earlier.sources):
            await self._parts.tools.sources.admit(work, payload, ())
        if kept is not None:
            earlier = await self._answers().fold(earlier, offer, kept)
        self._run.buffer.restore(earlier.text)
        self._begin(request, offer, labels, earlier.messages)

    def _answers(self) -> EgressAnswers:
        """What puts an approved call's result in place of its waiting answer."""
        tools, run = self._parts.tools, self._run
        reader = ResultReader((tools.pages, tools.sources, tools.bulkhead), (run.payload, run.work))
        return EgressAnswers(
            (self._parts.transactions, reader), (run.payload, run.work, run.emitter)
        )

    def _begin(
        self,
        request: ChatRequest,
        offer: TurnOffer,
        labels: list[tuple[Provenance, str]],
        earlier: tuple[ChatMessage, ...] = (),
    ) -> None:
        work = self._run.work
        work.offer = offer
        if self._run.payload.think_longer:
            request = replace(request, reasoning=ReasoningEffort.HIGH)
        for provenance, text in labels:
            work.read_wrapped(Label.of(provenance), unwrapped(text))
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
        scope, platform = payer_of(payload.scope())
        context = CallContext(
            effect_key=f"agent.turn:{payload.run_id}:{number}",
            feature="agent.turn",
            call_class=CallClass.STANDARD,
            origin=CallOrigin.INTERACTIVE,
            scope=scope,
            platform_account=platform,
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

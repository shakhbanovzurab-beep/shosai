"""One round of tool calls: checked, run at once within their limits, read back (Leo §8.3).

The model's calls of a round run in parallel, at most eight; the rest are refused, and so is
the last call of an answer the token limit cut, whose arguments may be incomplete. A write is
never run here, nor a call that sends data out once the run is tainted: the first such call of
the round is proposed as a card and pauses the run, any other is refused until the person
decides (`card_proposals`). A call of
a tool not offered, or with arguments its schema refuses, is answered with an error the model
can act on and never runs. A call runs within its tool's timeout and the turn's deadline,
through a bulkhead kept below the process's database pool, so a burst of calls waits for a
connection instead of failing for one; a failure is the model's to explain, never the run's
end. What the model reads of a result — its numbered sources, a digest of one over budget,
the wrapper of its label — is `tool_read_back`'s. The person sees each call that runs as a
step, the run's list of sources whenever a result adds to it, and each artifact a result hands
over by its reference (`artifact`, AG-R1), which the answer keeps.
"""

import asyncio
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from opentelemetry.trace import Tracer
from pydantic import BaseModel, JsonValue

from shosai.core.agent_tools.arguments import parse_arguments
from shosai.core.agent_tools.bindings import ReadTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import ToolError, ToolErrorCode, ToolResult
from shosai.core.agent_tools.sources import ArtifactKind, ArtifactRef
from shosai.core.ai.requests import ChatMessage, Role, TextPart, ToolCall
from shosai.features.agent.application.action_proposal import ActionProposer
from shosai.features.agent.application.card_proposals import CardProposals
from shosai.features.agent.application.result_pages import ResultPages
from shosai.features.agent.application.run_sources import RunSources, listed
from shosai.features.agent.application.run_work import CallAnswer, Round, RunWork, Step
from shosai.features.agent.application.tool_answers import (
    error_content,
    named,
    refusal_content,
    step_detail,
)
from shosai.features.agent.application.tool_offer import TurnOffer
from shosai.features.agent.application.tool_read_back import ResultReader
from shosai.features.agent.application.tool_registry import OfferedTool, waits_for_card
from shosai.features.agent.application.turn_task import RunEmitter, TurnPayload
from shosai.features.agent.domain.budgets import CALLS_PER_ROUND, estimate_tokens
from shosai.features.agent.domain.charts import SPEC_FIELD
from shosai.features.agent.domain.core_tools import LOAD_TOOLSET, NAVIGATE
from shosai.features.agent.domain.runs import TURN_DEADLINE
from shosai.features.agent.domain.stream import EventKind
from shosai.features.agent.domain.threads import StepStatus
from shosai.features.agent.infrastructure.prompts import (
    CUT_CALL,
    EXTRA_CALL,
    ONE_CHANGE,
    UNKNOWN_TOOL,
)
from shosai.features.agent.infrastructure.tool_metrics import ToolMetrics
from shosai.features.agent.infrastructure.turn_graph import LENGTH_FINISH, ModelAnswer

log = structlog.stdlib.get_logger(__name__)
OK = "ok"


@dataclass(frozen=True, slots=True)
class ToolParts:
    """What a round works with: kept results, the run's sources, the bulkhead, numbers and
    spans, and the proposer of writes."""

    pages: ResultPages
    sources: RunSources
    bulkhead: asyncio.Semaphore
    metrics: ToolMetrics
    tracer: Tracer
    proposer: ActionProposer


def artifact_of(artifact: ArtifactRef) -> dict[str, JsonValue]:
    """An artifact as the stream and the answer carry it: its reference, never its content —
    a chart with its spec as an object, as the cabinet draws it."""
    fields: dict[str, JsonValue] = dict(artifact.fields)
    if artifact.kind is ArtifactKind.CHART:
        fields[SPEC_FIELD] = json.loads(artifact.fields[SPEC_FIELD])
    return {"kind": artifact.kind.value, "ref": artifact.ref, "alt": artifact.alt, **fields}


class ToolRound:
    """Runs the calls of one model answer for one run."""

    def __init__(
        self,
        parts: ToolParts,
        run: tuple[TurnPayload, RunWork, RunEmitter],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._parts = parts
        self._payload, self._work, self._emitter = run
        self._clock = clock
        self._reader = ResultReader(
            (parts.pages, parts.sources, parts.bulkhead), (self._payload, self._work)
        )

    async def run(self, number: int, answer: ModelAnswer) -> tuple[ChatMessage, ...]:
        """The model's message and an answer to each of its calls, in their order."""
        offer = self._offer()
        calls = tuple(named(call, number, index) for index, call in enumerate(answer.tool_calls))
        cut = answer.finish_reason == LENGTH_FINISH
        context = ToolContext(
            self._payload.scope(), self._payload.run_id,
            self._payload.started_at + TURN_DEADLINE, self._work.taint,
        )  # fmt: skip
        # Заражение — на начало раунда: аргументы вызовов написаны до того, что раунд прочтёт.
        cards = [
            i for i, c in enumerate(calls) if waits_for_card(offer.tool(c.name), context.taint)
        ]
        answers = await asyncio.gather(
            *(
                self._answer(
                    offer, call, context,
                    refused=self._refusal(offer, calls, index, cut=cut)
                    or (refusal_content("one_change", ONE_CHANGE) if index in cards[1:] else None),
                    card=index in cards[:1],
                )
                for index, call in enumerate(calls)
            )
        )  # fmt: skip
        self._work.rounds.append(Round(datetime.now(UTC), answer.text, calls, tuple(answers)))
        parts = (TextPart(answer.text),) if answer.text else ()
        return (
            ChatMessage(Role.ASSISTANT, parts, tool_calls=calls),
            *(
                ChatMessage(Role.TOOL, (TextPart(each.content),), tool_call_id=each.call_id)
                for each in answers
            ),
        )

    def _offer(self) -> TurnOffer:
        if self._work.offer is None:
            message = "раунд инструментов до выбора наборов"
            raise RuntimeError(message)
        return self._work.offer

    @staticmethod
    def _refusal(
        offer: TurnOffer, calls: tuple[ToolCall, ...], index: int, *, cut: bool
    ) -> str | None:
        if index >= CALLS_PER_ROUND:
            return refusal_content("too_many_calls", EXTRA_CALL)
        if offer.tool(calls[index].name) is None:
            return refusal_content("unknown_tool", UNKNOWN_TOOL)
        if cut and index == len(calls) - 1:
            return refusal_content("cut_call", CUT_CALL)
        return None

    async def _answer(
        self,
        offer: TurnOffer,
        call: ToolCall,
        context: ToolContext,
        *,
        refused: str | None,
        card: bool,
    ) -> CallAnswer:
        offered = offer.tool(call.name)
        if refused is not None or offered is None:
            return CallAnswer(call.call_id, call.name, refused or "")
        spec = offered.spec
        arguments = parse_arguments(spec, call.arguments)
        if isinstance(arguments, ToolError):
            return CallAnswer(call.call_id, spec.name, error_content(arguments))
        if card:
            offer.called(offered)
            parts = (self._parts.proposer, self._parts.metrics)
            proposals = CardProposals(parts, (self._payload, self._work, self._emitter))
            return await proposals.answer(call, offered.tool, arguments, context)
        if spec.name == LOAD_TOOLSET and not offer.may_load(str(getattr(arguments, "name", ""))):
            invalid = ToolError(ToolErrorCode.INVALID_ARGUMENTS, {"fields": "name"})
            return CallAnswer(call.call_id, spec.name, error_content(invalid))
        seq = self._work.open_step()
        opened: dict[str, JsonValue] = {"id": f"step-{seq}", "seq": seq, "activity": spec.name}
        detail = step_detail(spec, arguments)
        await self._emitter.emit(EventKind.STEP_STARTED, opened | {"detail": detail})
        began = self._clock()
        attributes = {"tool.effect": spec.effect.value}
        name = f"tool.{spec.name}"
        with self._parts.tracer.start_as_current_span(name, attributes=attributes) as span:
            result = await self._execute(offered, arguments, context)
            offer.called(offered)
            read = await self._reader.read(offer, offered, result, context)
            outcome = OK if result.error is None else result.error.code.value
            span.set_attribute("tool.outcome", outcome)
            span.set_attribute("tool.result_tokens", estimate_tokens(read.text))
        seconds = self._clock() - began
        self._parts.metrics.called(spec.toolset, spec.effect.value, outcome, seconds)
        status = StepStatus.DONE if result.error is None else StepStatus.FAILED
        step = Step(seq, spec.name, detail, status.value, int(seconds * 1000),
                    None if result.error is None else outcome)  # fmt: skip
        self._work.steps.append(step)
        closed = opened | {"duration_ms": step.duration_ms}
        if result.error is None:
            await self._emitter.emit(EventKind.STEP_COMPLETED, closed)
            await self._follow(offer, spec.name, result.output)
            for artifact in result.artifacts:
                handed = artifact_of(artifact)
                self._work.artifacts.append(handed)
                await self._emitter.emit(EventKind.ARTIFACT, handed)
        else:
            await self._emitter.emit(EventKind.STEP_FAILED, closed | {"code": outcome})
        if read.new_sources:
            sources = listed(self._work, self._payload.language)
            await self._emitter.emit(EventKind.SOURCES, {"sources": list(sources)})
        return CallAnswer(call.call_id, spec.name, read.text, read.result_id)

    async def _execute(
        self, offered: OfferedTool, arguments: BaseModel, context: ToolContext
    ) -> ToolResult[Any]:
        """The tool's result within its timeout; a failure as its typed error."""
        spec, tool = offered.spec, offered.tool
        if not isinstance(tool, ReadTool):
            return ToolResult.failed(ToolErrorCode.FAILED)
        limit = min(spec.timeout.total_seconds(), context.remaining_seconds())
        try:
            async with asyncio.timeout(max(limit, 0.0)), self._parts.bulkhead:
                return await tool.run(arguments, context)
        except TimeoutError:
            return ToolResult.failed(ToolErrorCode.TIMEOUT)
        # Сбой инструмента — ошибка для модели, не конец хода; стек — в журнал.
        except Exception:
            log.exception("Инструмент Leo упал", tool=spec.name)
            return ToolResult.failed(ToolErrorCode.FAILED)

    async def _follow(self, offer: TurnOffer, name: str, output: BaseModel | None) -> None:
        """What the turn itself does after `load_toolset` and `navigate`."""
        if name == LOAD_TOOLSET and output is not None:
            loaded = str(getattr(output, "loaded", ""))
            if loaded in offer.deferred:
                offer.load(loaded)
                self._parts.metrics.loaded()
        elif name == NAVIGATE and output is not None:
            path = str(getattr(output, "to", ""))
            await self._emitter.emit(EventKind.CLIENT_ACTION, {"navigate": {"to": path}})

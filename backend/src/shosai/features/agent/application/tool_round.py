"""One round of tool calls: checked, run at once within their limits, read back (Leo §8.3).

The model's calls of a round run in parallel, at most eight; the rest are refused, and so is
the last call of an answer the token limit cut, whose arguments may be incomplete. A call of
a tool not offered, or with arguments its schema refuses, is answered with an error the model
can act on and never runs. A call runs within its tool's timeout and the turn's deadline,
through a bulkhead kept below the process's database pool, so a burst of calls waits for a
connection instead of failing for one; a failure is the model's to explain, never the run's
end. A result over its tool's budget is kept whole and read as a digest with its reference; a
result with a provenance — a page of a kept one with its tool's — is wrapped with the run's
boundary and raises the run's taint. The person sees each call that runs as a step.
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

import structlog
from opentelemetry.trace import Tracer
from pydantic import BaseModel, JsonValue

from shosai.core.agent_tools.arguments import parse_arguments
from shosai.core.agent_tools.bindings import ReadTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import ToolError, ToolErrorCode, ToolResult
from shosai.core.agent_tools.spec import Provenance
from shosai.core.ai.requests import ChatMessage, Role, TextPart, ToolCall
from shosai.features.agent.application.result_pages import ResultPages
from shosai.features.agent.application.run_work import CallAnswer, Round, RunWork, Step
from shosai.features.agent.application.tool_answers import (
    digest_content,
    error_content,
    named,
    refusal_content,
    step_detail,
)
from shosai.features.agent.application.tool_offer import TurnOffer
from shosai.features.agent.application.tool_registry import OfferedTool
from shosai.features.agent.application.turn_task import RunEmitter, TurnPayload
from shosai.features.agent.domain.budgets import CALLS_PER_ROUND, estimate_tokens, over_budget
from shosai.features.agent.domain.core_tools import LOAD_TOOLSET, NAVIGATE, READ_RESULT
from shosai.features.agent.domain.runs import TURN_DEADLINE
from shosai.features.agent.domain.stream import EventKind
from shosai.features.agent.domain.threads import StepStatus
from shosai.features.agent.domain.wrapper import Label, taint_after, wrap
from shosai.features.agent.infrastructure.prompts import CUT_CALL, EXTRA_CALL, UNKNOWN_TOOL
from shosai.features.agent.infrastructure.tool_metrics import ToolMetrics
from shosai.features.agent.infrastructure.turn_graph import LENGTH_FINISH, ModelAnswer

log = structlog.stdlib.get_logger(__name__)
OK = "ok"


@dataclass(frozen=True, slots=True)
class ToolParts:
    """What a round works with: kept results, the bulkhead, numbers and spans."""

    pages: ResultPages
    bulkhead: asyncio.Semaphore
    metrics: ToolMetrics
    tracer: Tracer


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

    async def run(self, number: int, answer: ModelAnswer) -> tuple[ChatMessage, ...]:
        """The model's message and an answer to each of its calls, in their order."""
        offer = self._offer()
        calls = tuple(named(call, number, index) for index, call in enumerate(answer.tool_calls))
        cut = answer.finish_reason == LENGTH_FINISH
        context = ToolContext(
            self._payload.scope(), self._payload.run_id,
            self._payload.started_at + TURN_DEADLINE, self._work.taint,
        )  # fmt: skip
        answers = await asyncio.gather(
            *(
                self._answer(
                    offer, call, context, refused=self._refusal(offer, calls, index, cut=cut)
                )
                for index, call in enumerate(calls)
            )
        )
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
        self, offer: TurnOffer, call: ToolCall, context: ToolContext, *, refused: str | None
    ) -> CallAnswer:
        offered = offer.tool(call.name)
        if refused is not None or offered is None:
            return CallAnswer(call.call_id, call.name, refused or "")
        spec = offered.spec
        arguments = parse_arguments(spec, call.arguments)
        if isinstance(arguments, ToolError):
            return CallAnswer(call.call_id, spec.name, error_content(arguments))
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
            content, result_id = await self._read_back(offer, offered, result, context)
            outcome = OK if result.error is None else result.error.code.value
            span.set_attribute("tool.outcome", outcome)
            span.set_attribute("tool.result_tokens", estimate_tokens(content))
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
        else:
            await self._emitter.emit(EventKind.STEP_FAILED, closed | {"code": outcome})
        return CallAnswer(call.call_id, spec.name, content, result_id)

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

    async def _read_back(
        self, offer: TurnOffer, offered: OfferedTool, result: ToolResult[Any], context: ToolContext
    ) -> tuple[str, UUID | None]:
        """What the model reads: the result, its digest or its error, wrapped by provenance."""
        if result.output is None:
            return error_content(result.error or ToolError(ToolErrorCode.FAILED)), None
        spec = offered.spec
        text, result_id = result.output.model_dump_json(), cast("UUID | None", None)
        if spec.name != READ_RESULT and over_budget(estimate_tokens(text), spec.result_budget):
            spaces = frozenset(s.org_id for s in result.sources if s.org_id is not None)
            async with self._parts.bulkhead:
                result_id = await self._parts.pages.keep(
                    context, spec.name, text, spaces if result.sources else None
                )
            dumped = result.output.model_dump(mode="json")
            text = digest_content(dumped, spec.result_budget, result_id)
        provenance = self._provenance(offer, offered, result)
        if provenance is not None:
            label = Label.of(provenance)
            text = wrap(text, label, self._work.token)
            self._work.taint = taint_after(self._work.taint, label)
        return text, result_id

    @staticmethod
    def _provenance(
        offer: TurnOffer, offered: OfferedTool, result: ToolResult[Any]
    ) -> Provenance | None:
        if offered.spec.name != READ_RESULT:
            return offered.spec.provenance
        origin = offer.kept_from(str(getattr(result.output, "tool", "")))
        # Инструмента хранимого результата больше нет: это прочитанное раньше, метка памяти.
        return origin.spec.provenance if origin is not None else Provenance.MEMORY

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

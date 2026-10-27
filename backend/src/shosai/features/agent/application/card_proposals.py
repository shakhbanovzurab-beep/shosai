"""A call in a round that waits for the person: proposed as a card, never run (Leo §5.3, §7.4;
agent steps 9a, 13b).

A write always waits; a call that sends data out waits once the run has read text from
outside Shosai. The person sees the proposal as a step; a write's slice plans and previews it
within the tool's timeout and the turn's deadline, and a refusal — arguments the slice cannot
plan, a target the person may not touch — goes back to the model as a typed error it can act
on, with no card. A proposal is stored as an action, announced by `action.proposed` with its
card, and the run pauses after the round: the model reads only that the person now decides.
"""

import asyncio
import time
from collections.abc import Callable

import structlog
from pydantic import BaseModel, JsonValue

from shosai.core.agent_tools.bindings import AgentTool, ReadTool, WriteTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import ToolError, ToolErrorCode
from shosai.core.ai.requests import ToolCall
from shosai.features.agent.application.action_proposal import ActionProposer, Proposed
from shosai.features.agent.application.run_work import CallAnswer, RunWork, Step
from shosai.features.agent.application.tool_answers import error_content, step_detail
from shosai.features.agent.application.turn_task import Emitter, TurnPayload
from shosai.features.agent.domain.stream import EventKind
from shosai.features.agent.domain.threads import StepStatus
from shosai.features.agent.infrastructure.prompts import CALL_PROPOSED, PROPOSED
from shosai.features.agent.infrastructure.tool_metrics import ToolMetrics

OUTCOME_PROPOSED = "proposed"
log = structlog.stdlib.get_logger(__name__)


class CardProposals:
    """Proposes the calls of one round that wait for the person."""

    def __init__(
        self,
        parts: tuple[ActionProposer, ToolMetrics],
        run: tuple[TurnPayload, RunWork, Emitter],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._proposer, self._metrics = parts
        self._payload, self._work, self._emitter = run
        self._clock = clock

    async def answer(
        self,
        call: ToolCall,
        tool: AgentTool,
        arguments: BaseModel,
        context: ToolContext,
    ) -> CallAnswer:
        """What the model reads back for its call: the card is up, or why not."""
        spec, work = tool.spec, self._work
        seq = work.open_step()
        opened: dict[str, JsonValue] = {"id": f"step-{seq}", "seq": seq, "activity": spec.name}
        detail = step_detail(spec, arguments)
        await self._emitter.emit(EventKind.STEP_STARTED, opened | {"detail": detail})
        began = self._clock()
        proposed = await self._proposed(tool, arguments, (call.call_id, context))
        seconds = self._clock() - began
        outcome = OUTCOME_PROPOSED if isinstance(proposed, Proposed) else proposed.code.value
        self._metrics.called(spec.toolset, spec.effect.value, outcome, seconds)
        failed = isinstance(proposed, ToolError)
        status = StepStatus.FAILED if failed else StepStatus.DONE
        step = Step(seq, spec.name, detail, status.value, int(seconds * 1000),
                    outcome if failed else None)  # fmt: skip
        work.steps.append(step)
        closed = opened | {"duration_ms": step.duration_ms}
        if isinstance(proposed, ToolError):
            await self._emitter.emit(EventKind.STEP_FAILED, closed | {"code": outcome})
            return CallAnswer(call.call_id, spec.name, error_content(proposed))
        work.proposed = proposed.record.id
        work.cards.append(proposed.record.id)
        await self._emitter.emit(EventKind.STEP_COMPLETED, closed)
        await self._emitter.emit(EventKind.ACTION_PROPOSED, {"action": proposed.card})
        waiting = PROPOSED if isinstance(tool, WriteTool) else CALL_PROPOSED
        return CallAnswer(call.call_id, spec.name, waiting)

    async def _proposed(
        self, tool: AgentTool, arguments: BaseModel, call: tuple[str, ToolContext]
    ) -> Proposed | ToolError:
        """The proposal within the tool's timeout; a slice's failure as a typed error."""
        call_id, context = call
        run = (self._payload, self._work)
        if isinstance(tool, ReadTool):
            return await self._proposer.propose_call(tool, arguments, call_id, run)
        limit = min(tool.spec.timeout.total_seconds(), context.remaining_seconds())
        try:
            async with asyncio.timeout(max(limit, 0.0)):
                return await self._proposer.propose(tool, arguments, context, run)
        except TimeoutError:
            return ToolError(ToolErrorCode.TIMEOUT)
        # Сбой среза при планировании — ошибка для модели, не конец хода; стек — в журнал.
        except Exception:
            log.exception("Запись Leo не спланирована", tool=tool.spec.name)
            return ToolError(ToolErrorCode.FAILED)

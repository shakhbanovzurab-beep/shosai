"""The models an evaluated turn talks to: CI's scripted double, and a recorder around any model
(AG-D8).

The scripted double plays a scenario's rounds in order — tool calls by their wire names, then
the answer's text — and reports tokens estimated from what it was sent, so CI needs no key and
spends nothing. The recorder sits between the engine and the model, scripted or real, and
keeps what each call read, which tools it was offered, which it called and what it used.
"""

import json
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Final

from shosai.core.ai.calls import CallContext, ModelRef, ModelRoute, Provider
from shosai.core.ai.requests import ChatRequest, TextPart, ToolCall
from shosai.core.ai.results import ChatDelta, Usage
from shosai.features.agent.application.run_engine_parts import ModelStreams
from shosai.features.agent.application.tool_registry import WIRE_DOT, wire_name
from shosai.features.agent.domain.budgets import estimate_tokens
from shosai.features.agent.domain.eval_cases import EvalRound
from shosai.features.agent.domain.eval_checks import ModelCall

SCRIPTED: Final = ModelRef(Provider.OPENROUTER, "eval/scripted")
SCRIPTED_ROUTE: Final = ModelRoute(SCRIPTED)
STOP: Final = "stop"
TOOL_CALLS: Final = "tool_calls"


def dotted(wire: str) -> str:
    """A tool's name from its wire name."""
    return wire.replace(WIRE_DOT, ".")


def request_text(request: ChatRequest) -> str:
    """Everything the model reads in the call's messages, as one text."""
    lines: list[str] = []
    for message in request.messages:
        lines.append(f"[{message.role.value}]")
        lines.extend(part.text for part in message.parts if isinstance(part, TextPart))
        lines.extend(f"{call.name}({call.arguments})" for call in message.tool_calls)
    return "\n".join(lines)


def tools_text(request: ChatRequest) -> str:
    """The call's tools as the model reads them: names, descriptions and schemas."""
    schemas = [
        {"name": tool.name, "description": tool.description, "parameters": tool.parameters}
        for tool in request.tools
    ]
    return json.dumps(schemas, ensure_ascii=False, sort_keys=True)


def input_tokens(request: ChatRequest) -> int:
    """The call's input, estimated as the context's segments are."""
    return estimate_tokens(request_text(request)) + estimate_tokens(tools_text(request))


class ScriptedRounds:
    """CI's model: the scenario's rounds in order, the last one for any call after them."""

    def __init__(self, rounds: Sequence[EvalRound]) -> None:
        if not rounds:
            message = "сценарий модели не пуст"
            raise ValueError(message)
        self._rounds = tuple(rounds)
        self._played = 0

    async def stream_chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> AsyncIterator[ChatDelta]:
        """The next round, as a model would stream it."""
        del context, route
        step = self._rounds[min(self._played, len(self._rounds) - 1)]
        self._played += 1
        read = input_tokens(request)
        if step.say is not None:
            yield ChatDelta(text=step.say)
            written = Usage(input_tokens=read, output_tokens=estimate_tokens(step.say))
            yield ChatDelta(finish_reason=STOP, usage=written, model=SCRIPTED)
            return
        calls = tuple(
            ToolCall(
                f"call-{self._played}-{index}",
                wire_name(call.tool),
                json.dumps(call.arguments, ensure_ascii=False, sort_keys=True),
            )
            for index, call in enumerate(step.calls)
        )
        written = Usage(
            input_tokens=read,
            output_tokens=sum(estimate_tokens(call.name + call.arguments) for call in calls),
        )
        yield ChatDelta(finish_reason=TOOL_CALLS, usage=written, model=SCRIPTED, tool_calls=calls)


@dataclass
class RecordingModel:
    """A model with every call noted: what it read and was offered, what it called and used."""

    inner: ModelStreams
    calls: list[ModelCall] = field(default_factory=list)
    attempted: list[str] = field(default_factory=list)
    requests: list[ChatRequest] = field(default_factory=list)

    async def stream_chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> AsyncIterator[ChatDelta]:
        """The inner model's answer, passed on piece by piece."""
        self.requests.append(request)
        usage: Usage | None = None
        called: tuple[ToolCall, ...] = ()
        async for delta in self.inner.stream_chat(context, route, request):
            usage = delta.usage or usage
            called = delta.tool_calls or called
            yield delta
        self.attempted.extend(dotted(call.name) for call in called)
        self.calls.append(
            ModelCall(
                text=request_text(request),
                tools=tuple(dotted(tool.name) for tool in request.tools),
                input_tokens=input_tokens(request),
                output_tokens=usage.output_tokens if usage is not None else 0,
                cost_usd=usage.reported_cost_usd if usage is not None else None,
            )
        )

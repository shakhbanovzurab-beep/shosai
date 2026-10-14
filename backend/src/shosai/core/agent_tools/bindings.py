"""A spec bound to the slice's handlers: what `FeatureParts.agent_tools` carries.

A read, egress or client tool has one handler, `run`. A write has three (Leo §8.1):
`plan` freezes the exact targets when the action is proposed, `preview` describes the plan
in i18n keys, `execute` applies the plan — and only the plan — under the principal's
scope, once per idempotency key, writing the key and the audit event in the same
transaction. The agent calls `execute` only through its Action Gateway, so a write never
runs without the approval the gateway asks for.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import PlannedEffect, Preview, ToolError, ToolResult
from shosai.core.agent_tools.spec import ToolEffect, ToolSpec

type RunHandler[I, O: BaseModel] = Callable[[I, ToolContext], Awaitable[ToolResult[O]]]
type PlanHandler[I] = Callable[[I, ToolContext], Awaitable[PlannedEffect | ToolError]]
type PreviewHandler = Callable[[PlannedEffect, ToolContext], Awaitable[Preview]]
type ExecuteHandler[O: BaseModel] = Callable[
    [PlannedEffect, ToolContext, str], Awaitable[ToolResult[O]]
]


@dataclass(frozen=True, slots=True)
class ReadTool[I: BaseModel, O: BaseModel]:
    """A tool that runs at once: read, egress or client."""

    spec: ToolSpec[I, O]
    run: RunHandler[I, O]

    def __post_init__(self) -> None:
        if self.spec.effect is ToolEffect.WRITE:
            message = f"инструмент {self.spec.name}: запись связывается как WriteTool"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class WriteTool[I: BaseModel, O: BaseModel]:
    """A tool that changes data: planned, previewed, then executed after approval."""

    spec: ToolSpec[I, O]
    plan: PlanHandler[I]
    preview: PreviewHandler
    execute: ExecuteHandler[O]

    def __post_init__(self) -> None:
        if self.spec.effect is not ToolEffect.WRITE:
            message = f"инструмент {self.spec.name}: WriteTool только для записи"
            raise ValueError(message)


type AgentTool = ReadTool[Any, Any] | WriteTool[Any, Any]

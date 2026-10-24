"""The tools a turn's tests offer Leo (agent step 6), and the model's script pieces for them.

`notes` searches meetings whose text is speech, waits past its timeout, or breaks; `tasks`
searches without a provenance and has a write that must never be offered; `files` is behind
a switch; `archive` is too large for segment 2 beside the others, so routing only names it
and the model has to load it.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field, create_model

from shosai.core.agent_tools.bindings import AgentTool, ReadTool, WriteTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.provenance import Provenance
from shosai.core.agent_tools.results import PlannedEffect, Preview, ToolResult
from shosai.core.agent_tools.sources import SourceRef
from shosai.core.agent_tools.spec import Reversibility, ToolEffect, ToolSpec
from shosai.core.ai.calls import ModelRef, Provider
from shosai.core.ai.requests import ToolCall
from shosai.core.ai.results import ChatDelta, Usage

USAGE: Final = Usage(input_tokens=10, output_tokens=2, reported_cost_usd=Decimal("0.0010"))
MODEL: Final = ModelRef(Provider.OPENROUTER, "probe/leo")


class Strict(BaseModel):
    """Arguments with no field the schema lacks."""

    model_config = ConfigDict(extra="forbid")


class Query(Strict):
    """What to look for."""

    query: str = Field(max_length=200, description="Words to look for.")


class Found(BaseModel):
    """What was found."""

    items: list[str]


# Сорок полей с длинными описаниями: схема набора не помещается в сегмент рядом с другими.
WIDE_FIELDS: Final[dict[str, Any]] = {
    f"field_{n}": (str | None, Field(default=None, description="An archive filter. " * 12))
    for n in range(40)
}
WIDE: Final = create_model("ArchiveQuery", __base__=Strict, **WIDE_FIELDS)


@dataclass(frozen=True, slots=True)
class Gates:
    """What sets a probe tool apart: its arguments, its label, its limits and its switch."""

    input: type[BaseModel] = Query
    step_detail: str | None = "query"
    provenance: Provenance | None = None
    result_budget: int = 2_000
    timeout: timedelta = timedelta(seconds=10)
    switch: str | None = None


PLAIN: Final = Gates()


def read(name: str, gates: Gates = PLAIN) -> ToolSpec[Any, Any]:
    """A read tool of the probe."""
    return ToolSpec(
        name=name, toolset=name.split(".", 1)[0], description=f"Probe tool {name}.",
        input=gates.input, output=Found, effect=ToolEffect.READ, provenance=gates.provenance,
        result_budget=gates.result_budget, timeout=gates.timeout, switch=gates.switch,
        step_detail=gates.step_detail,
    )  # fmt: skip


NOTES_SEARCH: Final = read(
    "notes.search", Gates(provenance=Provenance.MEETING_SPEECH, result_budget=200)
)
NOTES_WAIT: Final = read("notes.wait", Gates(timeout=timedelta(milliseconds=200)))
NOTES_FAIL: Final = read("notes.fail")
TASKS_SEARCH: Final = read("tasks.search")
FILES_SEARCH: Final = read("files.search", Gates(switch="agent.knowledge_base_search"))
ARCHIVE_SEARCH: Final = read("archive.search", Gates(input=WIDE, step_detail=None))
TASKS_CREATE: Final = ToolSpec(
    name="tasks.create", toolset="tasks", description="Probe write.", input=Query, output=Found,
    effect=ToolEffect.WRITE, reversibility=Reversibility.REVERSIBLE,
)  # fmt: skip


@dataclass
class ProbeTools:
    """The probe's handlers: what they return and which ran."""

    items: list[str] = field(default_factory=lambda: ["Budget review: travel cut by 20%"])
    ran: list[str] = field(default_factory=list)
    # Источники, которые называет каждый поиск.
    sources: list[SourceRef] = field(default_factory=list)

    async def search(self, arguments: Query, context: ToolContext) -> ToolResult[Found]:
        """The items and the sources, once per call."""
        del context
        self.ran.append(arguments.query)
        return ToolResult(Found(items=list(self.items)), sources=tuple(self.sources))

    async def archive(self, arguments: BaseModel, context: ToolContext) -> ToolResult[Found]:
        """The archive's items, noted as one run."""
        del arguments, context
        self.ran.append("archive")
        return ToolResult(Found(items=list(self.items)))

    async def wait(self, arguments: Query, context: ToolContext) -> ToolResult[Found]:
        """Longer than the tool's timeout."""
        del arguments, context
        await asyncio.sleep(5)
        return ToolResult(Found(items=[]))

    async def fail(self, arguments: Query, context: ToolContext) -> ToolResult[Found]:
        """A slice's bug."""
        del arguments, context
        message = "сбой инструмента-зонда"
        raise RuntimeError(message)

    def bound(self) -> tuple[AgentTool, ...]:
        """Every probe tool with its handler."""

        async def plan(arguments: Query, context: ToolContext) -> PlannedEffect:
            del arguments, context
            return PlannedEffect(targets=("probe",))

        async def preview(planned: PlannedEffect, context: ToolContext) -> Preview:
            del planned, context
            return Preview("agent.tasks.probe")

        async def execute(
            planned: PlannedEffect, context: ToolContext, key: str
        ) -> ToolResult[Found]:
            del planned, context, key
            return ToolResult(Found(items=[]))

        searches = (NOTES_SEARCH, TASKS_SEARCH, FILES_SEARCH)
        return (
            *(ReadTool(spec, self.search) for spec in searches),
            ReadTool(ARCHIVE_SEARCH, self.archive),
            ReadTool(NOTES_WAIT, self.wait),
            ReadTool(NOTES_FAIL, self.fail),
            WriteTool(TASKS_CREATE, plan, preview, execute),
        )


def calling(*calls: tuple[str, str], finish: str = "tool_calls") -> list[ChatDelta]:
    """A model round that calls tools by their wire names with JSON arguments."""
    made = tuple(ToolCall(f"call-{uuid.uuid4().hex[:8]}", name, args) for name, args in calls)
    return [ChatDelta(finish_reason=finish, usage=USAGE, model=MODEL, tool_calls=made)]


def saying(text: str) -> list[ChatDelta]:
    """A model round that answers."""
    return [ChatDelta(text=text), ChatDelta(finish_reason="stop", usage=USAGE, model=MODEL)]

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
from shosai.core.agent_tools.previews import LANGUAGES, PreviewField, PreviewWording
from shosai.core.agent_tools.provenance import Provenance
from shosai.core.agent_tools.results import (
    PlannedEffect,
    Preview,
    ToolError,
    ToolErrorCode,
    ToolResult,
)
from shosai.core.agent_tools.sources import ArtifactRef, SourceRef
from shosai.core.agent_tools.spec import CostClass, Reversibility, ToolEffect, ToolSpec
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
# Слова пробной записи: на всех языках одни, у карточки — заголовок и число.
PROBE_WORDING: Final = PreviewWording(
    key="agent.tasks.probe",
    params=("count",),
    title=dict.fromkeys(LANGUAGES, "Probe write"),
    fields=(PreviewField("count", dict.fromkeys(LANGUAGES, "Tasks")),),
)
# Пробное чтение платформы: набор оператора (AG-D5), человеку не предлагается никогда.
PLATFORM_PROBE: Final = read("platform.probe", Gates(step_detail=None))
# Пробный поиск в сети: выход наружу за переключателем, со своей карточкой.
WEB_LOOKUP: Final = ToolSpec(
    name="web.lookup", toolset="web", description="Probe egress.", input=Query, output=Found,
    effect=ToolEffect.EGRESS, cost_class=CostClass.METERED, switch="agent.web_search",
    provenance=Provenance.WEB, step_detail="query",
    previews=(
        PreviewWording(
            key="agent.web.lookup", params=("query",),
            title=dict.fromkeys(LANGUAGES, "Probe search"),
            fields=(PreviewField("query", dict.fromkeys(LANGUAGES, "Query")),),
        ),
    ),
)  # fmt: skip
TASKS_CREATE: Final = ToolSpec(
    name="tasks.create", toolset="tasks", description="Probe write.", input=Query, output=Found,
    effect=ToolEffect.WRITE, reversibility=Reversibility.REVERSIBLE, previews=(PROBE_WORDING,),
    invalidates=("tasks",),
)  # fmt: skip


@dataclass
class ProbeTools:
    """The probe's handlers: what they return and which ran."""

    items: list[str] = field(default_factory=lambda: ["Budget review: travel cut by 20%"])
    ran: list[str] = field(default_factory=list)
    # Ключи пунктов, которые запись действительно применила.
    executed: list[str] = field(default_factory=list)
    # Ворота записи: тест держит её посреди эффекта, чтобы «уронить» исполнителя.
    effect_gate: asyncio.Event = field(default_factory=asyncio.Event)
    refuse_plan: bool = False
    # Источники, которые называет каждый поиск.
    sources: list[SourceRef] = field(default_factory=list)
    # Артефакты, которые отдаёт каждый поиск (AG-R1).
    artifacts: list[ArtifactRef] = field(default_factory=list)
    # Страницы пробного поиска в сети; None — набора `web` у зонда нет.
    pages: list[SourceRef] | None = None

    async def search(self, arguments: Query, context: ToolContext) -> ToolResult[Found]:
        """The items and the sources, once per call."""
        del context
        self.ran.append(arguments.query)
        return ToolResult(
            Found(items=list(self.items)),
            sources=tuple(self.sources),
            artifacts=tuple(self.artifacts),
        )

    async def lookup(self, arguments: Query, context: ToolContext) -> ToolResult[Found]:
        """The pages found, noted as a search of the web."""
        del context
        self.ran.append(f"web:{arguments.query}")
        pages = self.pages or []
        return ToolResult(Found(items=[page.title for page in pages]), sources=tuple(pages))

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

    def __post_init__(self) -> None:
        self.effect_gate.set()

    def bound(self) -> tuple[AgentTool, ...]:
        """Every probe tool with its handler."""

        async def plan(arguments: Query, context: ToolContext) -> PlannedEffect | ToolError:
            del context
            if self.refuse_plan:
                return ToolError(ToolErrorCode.FORBIDDEN)
            return PlannedEffect(targets=("probe",), data={"query": arguments.query})

        async def preview(planned: PlannedEffect, context: ToolContext) -> Preview:
            del planned, context
            return Preview("agent.tasks.probe", {"count": 1})

        async def execute(
            planned: PlannedEffect, context: ToolContext, key: str
        ) -> ToolResult[Found]:
            del context
            await self.effect_gate.wait()
            if key not in self.executed:
                self.executed.append(key)
            return ToolResult(Found(items=[str(planned.data.get("query"))]))

        searches = (NOTES_SEARCH, TASKS_SEARCH, FILES_SEARCH)
        return (
            *(ReadTool(spec, self.search) for spec in searches),
            ReadTool(ARCHIVE_SEARCH, self.archive),
            ReadTool(NOTES_WAIT, self.wait),
            ReadTool(NOTES_FAIL, self.fail),
            WriteTool(TASKS_CREATE, plan, preview, execute),
            ReadTool(PLATFORM_PROBE, self.search),
            *((ReadTool(WEB_LOOKUP, self.lookup),) if self.pages is not None else ()),
        )


def calling(*calls: tuple[str, str], finish: str = "tool_calls") -> list[ChatDelta]:
    """A model round that calls tools by their wire names with JSON arguments."""
    made = tuple(ToolCall(f"call-{uuid.uuid4().hex[:8]}", name, args) for name, args in calls)
    return [ChatDelta(finish_reason=finish, usage=USAGE, model=MODEL, tool_calls=made)]


def saying(text: str) -> list[ChatDelta]:
    """A model round that answers."""
    return [ChatDelta(text=text), ChatDelta(finish_reason="stop", usage=USAGE, model=MODEL)]

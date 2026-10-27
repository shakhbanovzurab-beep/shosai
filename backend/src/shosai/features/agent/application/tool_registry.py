"""The tools a turn may offer the model, from core's catalog (Leo §8.2, ADR 0068 AG-D7; step 6).

Every bound tool of the process is in core's catalog, installed once all slices are built; the
registry reads it on the first turn and groups the tools by toolset in a fixed order — core,
notes, tasks, boards, files, account, then any other in the order it was bound — at most eight
to a toolset. Each name is spelled for the wire (`notes__search`: providers allow no dot), and its
schema is measured once. Reads, egress, cabinet actions and writes are offered; a write's call
becomes a card through the Action Gateway (step 9a), never an effect, and an egress call waits
for its card once the run is tainted (step 13b). A tool behind a switch the person turned off,
or an entitlement their plan lacks, is never offered; `platform` goes to the operator alone (AG-D5).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from shosai.core.agent_tools.bindings import AgentTool, WriteTool
from shosai.core.agent_tools.catalog import AgentToolCatalog
from shosai.core.agent_tools.context import Taint
from shosai.core.agent_tools.spec import ToolEffect, ToolSpec
from shosai.core.ai.requests import ToolSchema
from shosai.features.agent.domain.budgets import estimate_tokens
from shosai.features.agent.domain.digests import compact
from shosai.features.agent.domain.operator import offered_to
from shosai.features.agent.domain.routing import CORE
from shosai.features.agent.domain.wrapper import egress_needs_card

TOOLSET_ORDER: Final[tuple[str, ...]] = (CORE, "notes", "tasks", "boards", "files", "account")
TOOLS_PER_TOOLSET: Final = 8
OFFERED_EFFECTS: Final = frozenset(
    {ToolEffect.READ, ToolEffect.EGRESS, ToolEffect.CLIENT, ToolEffect.WRITE}
)
WIRE_DOT: Final = "__"
SOURCES_FIELD: Final = "sources"


def wire_name(name: str) -> str:
    """A tool's name as the provider takes it: `notes.search` → `notes__search`."""
    return name.replace(".", WIRE_DOT)


@dataclass(frozen=True, slots=True)
class Gates:
    """What the person may use: the switches they left on, and their plan's capabilities."""

    switches_on: frozenset[str]
    # None — тариф не читался: ни один инструмент не требует возможности тарифа.
    capabilities: frozenset[str] | None = None
    # Ход оператора платформы: только набор `platform` (AG-D5); человеку он не предлагается.
    operator: bool = False

    def admit(self, spec: ToolSpec[Any, Any]) -> bool:
        """Whether the tool may be offered: to this caller, its switch on, its entitlement in
        the plan."""
        if not offered_to(spec.toolset, spec.name, operator=self.operator):
            return False
        if spec.switch is not None and spec.switch not in self.switches_on:
            return False
        if spec.entitlement is None:
            return True
        return self.capabilities is not None and spec.entitlement in self.capabilities


@dataclass(frozen=True, slots=True)
class OfferedTool:
    """A tool as a turn offers it: bound, spelled for the wire, its schema measured."""

    tool: AgentTool
    schema: ToolSchema
    tokens: int

    @property
    def spec(self) -> ToolSpec[Any, Any]:
        """The tool's spec."""
        return self.tool.spec


@dataclass(frozen=True, slots=True)
class Toolsets:
    """The offerable tools by toolset, in the fixed order."""

    by_name: Mapping[str, tuple[OfferedTool, ...]]

    @property
    def names(self) -> tuple[str, ...]:
        """The toolsets in their order."""
        return tuple(self.by_name)

    def admitted(self, name: str, gates: Gates) -> tuple[OfferedTool, ...]:
        """The toolset's tools the person may use."""
        return tuple(tool for tool in self.by_name.get(name, ()) if gates.admit(tool.spec))

    def named(self, name: str) -> OfferedTool | None:
        """An offerable tool by its spec's name."""
        tools = (tool for toolset in self.by_name.values() for tool in toolset)
        return next((tool for tool in tools if tool.spec.name == name), None)

    def needs_capabilities(self) -> bool:
        """Whether some tool waits for the plan's capabilities."""
        tools = (tool for toolset in self.by_name.values() for tool in toolset)
        return any(tool.spec.entitlement is not None for tool in tools)


class ToolRegistry:
    """Reads the catalog once, on the first turn that needs it."""

    def __init__(self, catalog: AgentToolCatalog) -> None:
        self._catalog = catalog
        self._toolsets: Toolsets | None = None

    def toolsets(self) -> Toolsets:
        """The offerable toolsets; a toolset of more than eight tools stops the turn."""
        if self._toolsets is None:
            self._toolsets = toolsets_of(self._catalog)
        return self._toolsets


def toolsets_of(catalog: AgentToolCatalog) -> Toolsets:
    """The catalog's offerable tools by toolset, in the fixed order."""
    bound = catalog.toolsets()
    order = [name for name in TOOLSET_ORDER if name in bound]
    order += [name for name in bound if name not in TOOLSET_ORDER]
    by_name: dict[str, tuple[OfferedTool, ...]] = {}
    for name in order:
        tools = catalog.toolset(name)
        if len(tools) > TOOLS_PER_TOOLSET:
            message = f"в наборе {name} {len(tools)} инструментов, предел {TOOLS_PER_TOOLSET}"
            raise ValueError(message)
        # Модель читает источники результата под этим ключом: у выхода инструмента его нет.
        taken = [tool.spec.name for tool in tools if SOURCES_FIELD in tool.spec.output.model_fields]
        if taken:
            message = f"у выхода {taken} есть поле {SOURCES_FIELD}: оно занято источниками"
            raise ValueError(message)
        by_name[name] = tuple(
            offered(tool) for tool in tools if tool.spec.effect in OFFERED_EFFECTS
        )
    return Toolsets(by_name)


def is_write(offered: OfferedTool | None) -> bool:
    """Whether an offered tool changes data: its call becomes a proposal."""
    return offered is not None and isinstance(offered.tool, WriteTool)


def waits_for_card(offered: OfferedTool | None, taint: Taint) -> bool:
    """Whether the call becomes a card: a write always, a call out once the run is tainted."""
    if offered is None:
        return False
    return is_write(offered) or (
        offered.spec.effect is ToolEffect.EGRESS and egress_needs_card(taint)
    )


def offered(tool: AgentTool) -> OfferedTool:
    """The tool with its wire schema and that schema's size."""
    spec = tool.spec
    schema = ToolSchema(wire_name(spec.name), spec.description, spec.input_schema())
    measured = compact({"name": schema.name, "description": schema.description,
                        "parameters": schema.parameters})  # fmt: skip
    return OfferedTool(tool, schema, estimate_tokens(measured))

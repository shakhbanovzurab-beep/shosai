"""Every bound tool of the process, for the agent: filled once all slices are built.

The agent is a slice like the others and imports none of them (ADR 0029 point 2): it gets
this catalog through `CoreServices` and reads it when a turn runs, after composition has
installed what every slice bound. A name used twice stops the start.
"""

from collections.abc import Iterable, Mapping
from types import MappingProxyType

from shosai.core.agent_tools.bindings import AgentTool


class AgentToolCatalog:
    """The tools by name and by toolset."""

    def __init__(self) -> None:
        self._tools: Mapping[str, AgentTool] | None = None

    def install(self, tools: Iterable[AgentTool]) -> None:
        """Register the tools once."""
        if self._tools is not None:
            message = "инструменты агента уже установлены"
            raise RuntimeError(message)
        found: dict[str, AgentTool] = {}
        for tool in tools:
            if tool.spec.name in found:
                message = f"инструмент агента {tool.spec.name} объявлен дважды"
                raise ValueError(message)
            found[tool.spec.name] = tool
        self._tools = MappingProxyType(found)

    def tool(self, name: str) -> AgentTool | None:
        """The tool of the name, or None for a name the model made up."""
        return self._installed().get(name)

    def toolset(self, name: str) -> tuple[AgentTool, ...]:
        """The tools of a toolset, in the order the slices bound them."""
        return tuple(tool for tool in self._installed().values() if tool.spec.toolset == name)

    def _installed(self) -> Mapping[str, AgentTool]:
        if self._tools is None:
            message = "инструменты агента читаются до установки: композиция не закончена"
            raise RuntimeError(message)
        return self._tools

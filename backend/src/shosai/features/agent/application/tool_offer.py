"""A turn's tools: the toolsets routing chose and those it only names (ADR 0068 AG-D7; step 6).

Routing reads in the run's own transaction: the toolsets the page brings — its path and the
subject it shows — and those the thread's last three runs called; then, while segment 2's
4 000 tokens hold, everything else the person may use, in the fixed order. What is left is
named in `core.load_toolset`'s description, which is not offered when nothing is left; a call
of it adds that toolset from the next round. The run's row keeps the choice, the toolsets
loaded and those called, so the next turns stick to what this one used.
"""

from collections.abc import Mapping
from dataclasses import replace
from typing import Any, Final

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.requests import ToolSchema
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.surface_digest import SubjectKind
from shosai.features.agent.application.tool_registry import (
    Gates,
    OfferedTool,
    ToolRegistry,
    Toolsets,
    is_write,
)
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.domain.context import clean_path
from shosai.features.agent.domain.core_tools import LOAD_TOOLSET
from shosai.features.agent.domain.routing import (
    Route,
    RouteFacts,
    ToolsetFacts,
    route,
    sticky_toolsets,
)
from shosai.features.agent.infrastructure.prompts import LOADABLE
from shosai.features.agent.infrastructure.run_records import AgentRunRecord
from shosai.features.billing.contracts import ENTITLEMENTS, EntitlementsUnavailableError

RUN = AgentRunRecord
STICKY_TURNS: Final = 3
# Раздел кабинета (`/app/<раздел>`) и наборы, которые он приносит.
SURFACE_TOOLSETS: Final[Mapping[str, str]] = {
    "meetings": "notes", "notes": "notes", "kanban": "tasks", "tasks": "tasks",
    "projects": "tasks", "file-manager": "files", "folders": "files", "billing": "account",
    "plans": "account", "upgrade": "account", "profile": "account",
}  # fmt: skip
SUBJECT_TOOLSETS: Final[Mapping[SubjectKind, str]] = {
    SubjectKind.MEETING: "notes",
    SubjectKind.TASK: "tasks",
    SubjectKind.BOARD: "tasks",
    SubjectKind.FILE: "files",
}
log = structlog.stdlib.get_logger(__name__)


class TurnOffer:
    """The run's tools: those offered now, those it may still load, those it called."""

    def __init__(self, toolsets: Toolsets, gates: Gates, chosen: Route) -> None:
        self._toolsets = toolsets
        self._gates = gates
        self.rule = chosen.rule
        self.selected = list(chosen.selected)
        self.deferred = list(chosen.deferred)
        # Наборы только для чтения: загрузка добавит их записи.
        self.reading = list(chosen.reading)
        self.loaded: list[str] = []
        self.used: list[str] = []
        # Наборы, в которые ход предложил запись: следующие ходы получают их целиком.
        self.wrote: list[str] = []
        self._tools = self._offered()

    def tool(self, wire: str) -> OfferedTool | None:
        """The offered tool of a wire name, or None for one the model made up."""
        return self._tools.get(wire)

    def schemas(self) -> tuple[ToolSchema, ...]:
        """The schemas sent this round; `load_toolset` lists what may still be loaded."""
        schemas: list[ToolSchema] = []
        for tool in self._tools.values():
            if tool.spec.name != LOAD_TOOLSET:
                schemas.append(tool.schema)
            elif self.deferred:
                listed = LOADABLE.format(names=", ".join(self.deferred))
                schemas.append(
                    replace(tool.schema, description=f"{tool.schema.description} {listed}")
                )
        return tuple(schemas)

    def tokens(self) -> int:
        """The estimated size of the schemas sent."""
        return sum(tool.tokens for tool in self._tools.values())

    def kept_from(self, name: str) -> OfferedTool | None:
        """The tool a kept result came from, by its spec's name; None for one gone since."""
        return self._toolsets.named(name)

    def may_load(self, name: str) -> bool:
        """Whether the toolset is one the run has or may still load."""
        return name in self.deferred or name in self.selected

    def load(self, name: str) -> None:
        """Add a named toolset from the next round."""
        if name in self.deferred:
            self.deferred.remove(name)
            if name in self.reading:
                self.reading.remove(name)
            self.selected.append(name)
            self.loaded.append(name)
            self._tools = self._offered()

    def called(self, tool: OfferedTool) -> None:
        """Note the toolset of a called tool: the next turns keep it, whole after a write."""
        toolset = tool.spec.toolset
        if toolset not in self.used:
            self.used.append(toolset)
        if is_write(tool) and toolset not in self.wrote:
            self.wrote.append(toolset)

    def routing(self) -> dict[str, object]:
        """What the run's row keeps: names and the rule's code."""
        return {"rule": self.rule, "selected": self.selected, "reading": self.reading,
                "deferred": self.deferred, "loaded": self.loaded, "used": self.used,
                "wrote": self.wrote}  # fmt: skip

    def _offered(self) -> dict[str, OfferedTool]:
        chosen, reading = set(self.selected), set(self.reading)
        return {
            tool.schema.name: tool
            for name in self._toolsets.names
            if name in chosen or name in reading
            for tool in self._toolsets.admitted(name, self._gates)
            if name in chosen or not is_write(tool)
        }


class TurnRouting:
    """Chooses a run's toolsets in its own transaction."""

    def __init__(self, registry: ToolRegistry, ports: PortDirectory) -> None:
        self._registry = registry
        self._ports = ports

    async def offer(self, session: AsyncSession, payload: TurnPayload) -> TurnOffer:
        """The run's offer: the page's, the sticky and then the others while they fit."""
        toolsets = self._registry.toolsets()
        gates = Gates(frozenset(payload.switches_on), await self._capabilities(payload, toolsets))
        facts = []
        for name in toolsets.names:
            admitted = toolsets.admitted(name, gates)
            reads = sum(tool.tokens for tool in admitted if not is_write(tool))
            total = sum(tool.tokens for tool in admitted)
            facts.append(ToolsetFacts(name, total, bool(admitted), read_tokens=reads))
        sticky, recent = await self._sticky(session, payload)
        chosen = route(
            RouteFacts(
                tuple(facts),
                surface=surface_toolsets(payload),
                sticky=sticky,
                recent=recent,
            )
        )
        return TurnOffer(toolsets, gates, chosen)

    async def _capabilities(
        self, payload: TurnPayload, toolsets: Toolsets
    ) -> frozenset[str] | None:
        """The plan's capabilities, read only when some tool needs one."""
        if not toolsets.needs_capabilities() or payload.user_id is None:
            return None
        try:
            snapshot = await self._ports.get(ENTITLEMENTS).snapshot(payload.home, payload.user_id)
        except EntitlementsUnavailableError:
            # Тариф не прочитан: инструменты с возможностью тарифа не предлагаются (inv-3).
            log.warning("Возможности тарифа для хода Leo не прочитаны")
            return frozenset()
        return frozenset(capability.value for capability in snapshot.capabilities)

    async def _sticky(
        self, session: AsyncSession, payload: TurnPayload
    ) -> tuple[frozenset[str], frozenset[str]]:
        """The toolsets the thread's last three runs wrote to, and those they read from."""
        rows = await session.scalars(
            select(RUN.routing)
            .where(
                RUN.thread_id == payload.thread_id,
                RUN.user_id == payload.user_id,
                RUN.started_at < payload.started_at,
            )
            .order_by(RUN.started_at.desc())
            .limit(STICKY_TURNS)
        )
        routings = list(rows)
        return (
            sticky_toolsets(names(routings, "wrote"), STICKY_TURNS),
            sticky_toolsets(names(routings, "used"), STICKY_TURNS),
        )


def names(routings: list[dict[str, Any]], key: str) -> list[frozenset[str]]:
    """Each run's toolsets under one key of its routing, newest run first."""
    return [
        frozenset(name for name in routing.get(key, ()) if isinstance(name, str))
        for routing in routings
    ]


def surface_toolsets(payload: TurnPayload) -> frozenset[str]:
    """The toolsets the page brings: its section and the subject it shows."""
    names: set[str] = set()
    path = clean_path(payload.path)
    if path is not None:
        parts = path.strip("/").split("/")
        if len(parts) > 1 and parts[0] == "app" and parts[1] in SURFACE_TOOLSETS:
            names.add(SURFACE_TOOLSETS[parts[1]])
    if payload.subject_kind is not None:
        names.add(SUBJECT_TOOLSETS[payload.subject_kind])
    return frozenset(names)

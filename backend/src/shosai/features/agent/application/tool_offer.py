"""A turn's tools: the toolsets routing chose and those it only names (ADR 0068 AG-D7; step 6).

Routing reads in the run's own transaction: the toolsets the page brings — its path and the
subject it shows — and those the thread's last three runs called; then, while segment 2's
4 000 tokens hold, everything else the person may use, in the fixed order — or, when that
order leaves one out and a router is bound, those it found the turn needs first
(`route_ranking.py`). What is left is named in `core.load_toolset`'s description, which is
not offered when nothing is left; a call of it adds that toolset from the next round. The
run's row keeps the choice, the toolsets loaded, routed and called, so the next turns stick
to what this one used.
"""

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any, Final

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.requests import ToolSchema
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.page_toolsets import page_section, surface_toolsets
from shosai.features.agent.application.route_ranking import Asked, RouteRanking
from shosai.features.agent.application.tool_registry import (
    Gates,
    OfferedTool,
    ToolRegistry,
    Toolsets,
    is_write,
)
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.domain.budgets import SEGMENT_CAPS, Segment
from shosai.features.agent.domain.core_tools import LOAD_TOOLSET
from shosai.features.agent.domain.operator import is_operator
from shosai.features.agent.domain.routing import (
    Route,
    RouteFacts,
    ToolsetFacts,
    candidates,
    route,
    sticky_toolsets,
    wanted,
)
from shosai.features.agent.infrastructure.prompts import LOADABLE
from shosai.features.agent.infrastructure.run_records import AgentRunRecord
from shosai.features.billing.contracts import ENTITLEMENTS, EntitlementsUnavailableError

RUN = AgentRunRecord
STICKY_TURNS: Final = 3
TOOLS_CAP: Final = SEGMENT_CAPS[Segment.TOOLS]
log = structlog.stdlib.get_logger(__name__)


class TurnOffer:
    """The run's tools: those offered now, those it may still load, those it called."""

    def __init__(
        self, toolsets: Toolsets, gates: Gates, chosen: Route, facts: RouteFacts | None = None
    ) -> None:
        self._toolsets = toolsets
        self._gates = gates
        self._facts = facts
        self.rule = chosen.rule
        self.selected = list(chosen.selected)
        self.deferred = list(chosen.deferred)
        # Наборы только для чтения: загрузка добавит их записи.
        self.reading = list(chosen.reading)
        self.loaded: list[str] = []
        self.used: list[str] = []
        # Наборы, в которые ход предложил запись: следующие ходы получают их целиком.
        self.wrote: list[str] = []
        # Наборы, которые привёл роутер: их чтение остаётся треду на три хода.
        self.routed: list[str] = []
        self.asked = False
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

    def to_rank(self) -> tuple[str, ...]:
        """The toolsets that fill the room, when the rule could not offer one of them even
        for reading (it is only named); else none — then every toolset's reads are here and
        its writes one `load_toolset` away (DL-D3: not asked while everything fits)."""
        names = candidates(self._facts) if self._facts is not None else ()
        offered = set(self.selected) | set(self.reading)
        return names if any(name not in offered for name in names) else ()

    def summary(self, name: str) -> str:
        """A toolset's tools and the first sentence of each one's registered description."""
        tools = self._toolsets.admitted(name, self._gates)
        return " ".join(
            f"{tool.spec.name}: {first_sentence(tool.spec.description)}" for tool in tools
        )

    def kept(self) -> tuple[int, int]:
        """How many toolsets the rule keeps whole, and the tokens of segment 2 left."""
        if self._facts is None:
            return 0, 0
        forced = wanted(self._facts) | self._facts.recent
        return len(forced & set(self.selected)), max(self._facts.cap - self.tokens(), 0)

    def rank(self, ranked: Sequence[str]) -> None:
        """Fill the room with the ranked toolsets first; those that came in are kept as routed."""
        if self._facts is None or not ranked:
            return
        chosen = route(self._facts, ranked)
        self.selected, self.deferred = list(chosen.selected), list(chosen.deferred)
        self.reading = list(chosen.reading)
        offered = set(self.selected) | set(self.reading)
        self.routed = [name for name in ranked if name in offered]
        self._tools = self._offered()

    def restore(self, routing: Mapping[str, Any]) -> None:
        """Go on with what a resumed run was routed to, loaded, called and wrote to before
        its card."""
        self.asked = routing.get("asked") is True
        self.rank(listed_names(routing, "routed"))
        for name in listed_names(routing, "loaded"):
            self.load(name)
        for kept, key in ((self.used, "used"), (self.wrote, "wrote")):
            kept.extend(name for name in listed_names(routing, key) if name not in kept)

    def routing(self) -> dict[str, object]:
        """What the run's row keeps: names and the rule's code."""
        return {"rule": self.rule, "selected": self.selected, "reading": self.reading,
                "deferred": self.deferred, "loaded": self.loaded, "used": self.used,
                "wrote": self.wrote, "routed": self.routed, "asked": self.asked}  # fmt: skip

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
        self._ranking = RouteRanking(ports)

    async def offer(
        self, session: AsyncSession, payload: TurnPayload, *, cap: int = TOOLS_CAP
    ) -> TurnOffer:
        """The run's offer: the page's, the sticky and then the others while they fit in `cap`
        tokens of schemas — wider for a voice session, which cannot load a toolset later."""
        toolsets = self._registry.toolsets()
        operator = is_operator(payload.user_id)
        capabilities = None if operator else await self._capabilities(payload, toolsets)
        gates = Gates(frozenset(payload.switches_on), capabilities, operator)
        facts = []
        for name in toolsets.names:
            admitted = toolsets.admitted(name, gates)
            reads = sum(tool.tokens for tool in admitted if not is_write(tool))
            total = sum(tool.tokens for tool in admitted)
            facts.append(ToolsetFacts(name, total, bool(admitted), read_tokens=reads))
        sticky, recent = await self._sticky(session, payload)
        kept = RouteFacts(
            tuple(facts), surface=surface_toolsets(payload), sticky=sticky, recent=recent, cap=cap
        )
        return TurnOffer(toolsets, gates, route(kept), kept)

    async def ask(
        self, session: AsyncSession, payload: TurnPayload, offer: TurnOffer
    ) -> Asked | None:
        """Start a bound router on what fills the offer's room; None when nothing is to rank."""
        return await self._ranking.ask(session, payload, offer, page_section(payload))

    async def settle(self, offer: TurnOffer, asked: Asked | None) -> None:
        """The router's ranking applied to the offer, within the turn's wait."""
        offer.asked = await self._ranking.settle(offer, asked)

    @staticmethod
    def drop(asked: Asked | None) -> None:
        """Stop waiting for a router the run no longer needs."""
        if asked is not None:
            asked.cancel()

    def ended(self, payload: TurnPayload, offer: TurnOffer | None) -> None:
        """Tell the router which toolsets a run it was asked about called."""
        if offer is not None and offer.asked:
            self._ranking.ended(payload, offer.used)

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
        read = [
            used | routed
            for used, routed in zip(names(routings, "used"), names(routings, "routed"), strict=True)
        ]
        return (
            sticky_toolsets(names(routings, "wrote"), STICKY_TURNS),
            sticky_toolsets(read, STICKY_TURNS),
        )


def listed_names(routing: Mapping[str, Any], key: str) -> list[str]:
    """The toolsets one run's routing lists under a key."""
    listed = routing.get(key, ())
    return [name for name in listed if isinstance(name, str)] if isinstance(listed, list) else []


def names(routings: list[dict[str, Any]], key: str) -> list[frozenset[str]]:
    """Each run's toolsets under one key of its routing, newest run first."""
    return [
        frozenset(name for name in routing.get(key, ()) if isinstance(name, str))
        for routing in routings
    ]


def first_sentence(description: str) -> str:
    """A description's first sentence."""
    head, _, _ = description.strip().partition(". ")
    return head if head.endswith(".") else f"{head}."

"""The run's sources: numbered for the model, named with their space for the person (AG-D1).

A tool names what its result rests on; the run numbers each new source in arrival order
(`domain/sources.py`) and hands the model those numbers inside the result, so an answer cites
`[n]` of a list the tools made — never one the model wrote. Each source is named with its
space: the workspace's name, or Personal in the answer's language. The person's workspaces and
their names are read once per run, in the person's transaction; a source from a workspace the
person is not in is dropped whatever the tool said, so nothing of another space is listed.
"""

from collections.abc import Mapping, Sequence
from uuid import UUID

import structlog
from pydantic import JsonValue

from shosai.core.agent_tools.sources import SourceRef
from shosai.core.db.transactions import HomeTransactions
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.run_work import RunWork
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.domain.spaces import space_of
from shosai.features.workspaces.contracts import MEMBERSHIP_READER, WORKSPACE_READER

log = structlog.stdlib.get_logger(__name__)


def cite(number: int, ref: SourceRef) -> dict[str, JsonValue]:
    """A source as the model reads it beside a result: its number and what it is."""
    entry: dict[str, JsonValue] = {"n": number, "kind": ref.kind.value, "id": ref.id,
                                   "title": ref.title}  # fmt: skip
    if ref.locator is not None:
        entry["locator"] = ref.locator
    return entry


class RunSources:
    """Numbers a run's sources and names their spaces."""

    def __init__(self, transactions: HomeTransactions, ports: PortDirectory) -> None:
        self._transactions = transactions
        self._ports = ports

    async def admit(
        self, work: RunWork, payload: TurnPayload, refs: Sequence[SourceRef]
    ) -> tuple[list[dict[str, JsonValue]], bool]:
        """What the model may cite of a result's sources, and whether the list grew."""
        spaces = await self._spaces(work, payload)
        kept = [ref for ref in refs if ref.org_id is None or ref.org_id in spaces]
        if len(kept) < len(refs):
            # Инструмент назвал источник пространства, где человека нет: в список он не идёт.
            log.warning("Источник чужого пространства отброшен", dropped=len(refs) - len(kept))
        before = len(work.sources.sources)
        work.sources, numbers = work.sources.add(kept)
        cites = [cite(n, ref) for n, ref in zip(numbers, kept, strict=True) if n is not None]
        return cites, len(work.sources.sources) > before

    async def _spaces(self, work: RunWork, payload: TurnPayload) -> Mapping[UUID, str]:
        """The person's workspaces by id, with their names; read once per run."""
        async with work.spaces_read:
            if work.spaces is None:
                user_id = payload.user_id
                if user_id is None:
                    message = "источники хода читаются от имени человека"
                    raise ValueError(message)
                async with self._transactions.begin(payload.scope(), read_only=True) as session:
                    active = await self._ports.get(MEMBERSHIP_READER).active(session, user_id)
                    facts = await self._ports.get(WORKSPACE_READER).workspaces(
                        session, [membership.org_id for membership in active]
                    )
                work.spaces = {org_id: fact.name for org_id, fact in facts.items()}
            return work.spaces


def listed(work: RunWork, language: str) -> list[dict[str, JsonValue]]:
    """The run's sources as the cabinet shows them, numbered by position."""
    spaces = work.spaces or {}
    return [
        {
            "id": ref.id, "kind": ref.kind.value, "title": ref.title,
            # Источник workspace допущен, только если его имя прочитано: оно всегда есть.
            "space": space_of(ref, language, spaces),
            "locator": ref.locator, "quote": ref.quote, "highlight": [],
        }
        for ref in work.sources.sources
    ]  # fmt: skip


def kept(work: RunWork, language: str) -> list[dict[str, JsonValue]]:
    """The run's sources as the answer's row keeps them: as listed, with their workspace."""
    return [
        entry | {"org_id": None if ref.org_id is None else str(ref.org_id)}
        for entry, ref in zip(listed(work, language), work.sources.sources, strict=True)
    ]

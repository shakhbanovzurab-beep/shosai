"""An action as the person's card reads it, in the stream, the inbox and the history (steps 9a, 9b).

The card carries what the person decides with, in their language (their profile's): the title
and the labelled fields its slice words for the preview it planned (`ToolSpec.previews`), the
space the change goes to — Personal, or the workspace by name — where the proposal came from,
how it can be undone, whether it asks for a careful decision on the screen, what the run read
before it (a label), its state and its times, the nonce a decision carries, and, once it has
run, the cabinet's data its succeeded items changed (`invalidates`) — so a screen re-reads
them wherever the card's outcome reaches it, in a run's stream or outside one. Every channel
renders the same words from the same wording, so no client keeps a slice's vocabulary.
"""

from collections.abc import Mapping, Sequence
from typing import Final
from uuid import UUID

import structlog
from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.catalog import AgentToolCatalog
from shosai.core.agent_tools.context import Taint
from shosai.core.agent_tools.previews import (
    EMPTY,
    FALLBACK_LANGUAGE,
    PreviewWording,
    RenderedPreview,
    render_preview,
)
from shosai.core.agent_tools.results import Preview
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.action_rows import items_of
from shosai.features.agent.domain.action_items import ActionItem, ItemState
from shosai.features.agent.domain.actions import ActionStatus, ProposalOrigin, public_status
from shosai.features.agent.domain.friction import Friction, screen_only
from shosai.features.agent.domain.spaces import personal_space
from shosai.features.agent.infrastructure.run_records import AgentActionRecord
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER
from shosai.features.workspaces.contracts import WORKSPACE_READER

# Откуда карточка для кабинета: и ход, и порт среза кладут её в тред.
ORIGIN_KINDS: Final[Mapping[ProposalOrigin, str]] = {
    ProposalOrigin.TURN: "thread",
    ProposalOrigin.PROPOSAL_PORT: "thread",
}
log = structlog.stdlib.get_logger(__name__)


def invalidated(catalog: AgentToolCatalog, items: Sequence[ActionItem]) -> tuple[str, ...]:
    """The cabinet's data domains the succeeded items changed, in their order."""
    domains: dict[str, None] = {}
    for item in items:
        tool = catalog.tool(item.tool)
        if item.state is ItemState.SUCCEEDED and tool is not None:
            domains |= dict.fromkeys(tool.spec.invalidates)
    return tuple(domains)


def card_of(
    record: AgentActionRecord, rendered: RenderedPreview, facts: tuple[str, tuple[str, ...]]
) -> dict[str, JsonValue]:
    """The card of an action, with its words rendered, in its space, with what it changed."""
    space, changed = facts
    items = items_of(record)
    first = items[0]
    codes = [item.code for item in items if item.state is not ItemState.SUCCEEDED and item.code]
    return {
        "id": str(record.id),
        "tool": first.tool,
        "title": rendered.title,
        "space": space,
        "origin": {"kind": ORIGIN_KINDS[ProposalOrigin(record.origin)], "app": None},
        "reversibility": first.reversibility,
        "warning": screen_only(Friction(record.friction)),
        "taint": record.taint_sources[0] if record.taint_sources else None,
        "suspicious": record.taint >= Taint.SUSPICIOUS,
        "preview": {
            "kind": "fields",
            "fields": [{"label": label, "value": value} for label, value in rendered.fields],
            "body": rendered.body,
        },
        "status": public_status(ActionStatus(record.status)).value,
        "outcome": codes[0] if codes else None,
        "nonce": record.nonce,
        "created_at": record.created_at.isoformat(),
        "expires_at": record.expires_at.isoformat(),
        "resolved_at": None if record.resolved_at is None else record.resolved_at.isoformat(),
        "invalidates": list(changed),
    }


class ActionCards:
    """Renders the person's actions into cards, in their language."""

    def __init__(self, catalog: AgentToolCatalog, ports: PortDirectory) -> None:
        self._catalog = catalog
        self._ports = ports

    async def cards(
        self,
        session: AsyncSession,
        records: Sequence[AgentActionRecord],
        language: str | None = None,
    ) -> list[dict[str, JsonValue]]:
        """The cards of one person's actions, in the order given, read in their transaction —
        in their profile's language, or in the one a caller asks for."""
        if not records:
            return []
        language = language or await self._language(session, records[0].user_id)
        spaces = await self._spaces(session, {r.org_id for r in records if r.org_id is not None})
        return [
            card_of(
                record,
                self.rendered(items_of(record)[0], language),
                (
                    personal_space(language)
                    if record.org_id is None
                    else spaces.get(record.org_id, EMPTY),
                    invalidated(self._catalog, items_of(record)),
                ),
            )
            for record in records
        ]

    def words(self, item: ActionItem, language: str) -> str:
        """The card as the person reads it: the title, the labelled fields and the body."""
        rendered = self.rendered(item, language)
        lines = [rendered.title, *(f"{label}: {value}" for label, value in rendered.fields)]
        if rendered.body:
            lines.append(rendered.body)
        return "\n".join(lines)

    def rendered(self, item: ActionItem, language: str) -> RenderedPreview:
        """The item's preview in the language; the tool's name when its slice has no words."""
        wording = self.wording(item.tool, item.preview_key)
        if wording is None:
            log.error("У превью записи Leo нет формулировки", tool=item.tool, key=item.preview_key)
            return RenderedPreview(title=item.tool, fields=())
        return render_preview(wording, Preview(item.preview_key, item.preview_params), language)

    def wording(self, tool: str, key: str) -> PreviewWording | None:
        """The slice's words for one preview key of its write tool."""
        found = self._catalog.tool(tool)
        if found is None:
            return None
        return next((wording for wording in found.spec.previews if wording.key == key), None)

    async def _language(self, session: AsyncSession, user_id: UUID) -> str:
        profile = await self._ports.get(ACCOUNT_PROFILE_READER).profile(session, user_id)
        return profile.language if profile is not None else FALLBACK_LANGUAGE

    async def _spaces(self, session: AsyncSession, org_ids: set[UUID]) -> Mapping[UUID, str]:
        if not org_ids:
            return {}
        facts = await self._ports.get(WORKSPACE_READER).workspaces(session, org_ids)
        return {org_id: fact.name for org_id, fact in facts.items()}

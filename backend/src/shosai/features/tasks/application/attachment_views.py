"""A task's attachments and its cover as a reader sees them (tasks plan §3.13; ADR 0064).

The rows say what each attachment is; the links to previews are files' to sign, and files
signs only after its own short read, so a view gets them after the reader's transaction
closes, in one call for a whole list: the covers of its cards and the images of a panel.
"""

from collections.abc import Mapping, Sequence
from dataclasses import replace
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.files.contracts.held_objects import HELD_OBJECTS
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER
from shosai.features.tasks.application.task_parts import AttachmentView, PersonRef
from shosai.features.tasks.application.views import CardView, TaskView
from shosai.features.tasks.infrastructure.attachment_records import TaskAttachmentRecord

ATTACHMENTS = TaskAttachmentRecord


async def attachments_of(
    session: AsyncSession, ports: PortDirectory, task_id: UUID
) -> tuple[AttachmentView, ...]:
    """The task's attachments in the order they were added, with who added each."""
    rows = list(
        await session.scalars(
            select(ATTACHMENTS)
            .where(ATTACHMENTS.task_id == task_id)
            .order_by(ATTACHMENTS.added_at, ATTACHMENTS.id)
        )
    )
    adders = {row.added_by for row in rows}
    names = await ports.get(ACCOUNT_PROFILE_READER).names(session, adders) if adders else {}
    return tuple(attachment_of(row, names) for row in rows)


def attachment_of(row: TaskAttachmentRecord, names: Mapping[UUID, str]) -> AttachmentView:
    """One attachment's view."""
    return AttachmentView(
        id=row.id,
        held_object_id=row.held_object_id,
        name=row.name,
        content_type=row.content_type,
        size_bytes=row.size_bytes,
        image=row.image,
        added_by=PersonRef(row.added_by, names.get(row.added_by, "")),
        added_at=row.added_at,
    )


async def with_previews(
    ports: PortDirectory, scope: TenancyScope, views: Sequence[TaskView]
) -> list[TaskView]:
    """The views with the links of their covers' and images' previews, signed after the
    reader's transaction; one call to files for all of them."""
    held = {view.card.cover.held_object_id for view in views if view.card.cover is not None}
    held |= {
        attachment.held_object_id
        for view in views
        for attachment in view.attachments
        if attachment.image
    }
    if not held:
        return list(views)
    urls = await ports.get(HELD_OBJECTS).previews(scope, held)
    return [_previewed(view, urls) for view in views]


def _previewed(view: TaskView, urls: Mapping[UUID, str]) -> TaskView:
    cover = view.card.cover
    card = (
        view.card
        if cover is None
        else replace(view.card, cover=replace(cover, preview_url=urls.get(cover.held_object_id)))
    )
    attachments = tuple(
        replace(attachment, preview_url=urls.get(attachment.held_object_id))
        for attachment in view.attachments
    )
    return replace(view, card=card, attachments=attachments)


async def with_cover_previews(
    ports: PortDirectory, scope: TenancyScope, cards: Sequence[CardView]
) -> list[CardView]:
    """The cards with their covers' preview links, signed after the reader's transaction."""
    held = {card.cover.held_object_id for card in cards if card.cover is not None}
    if not held:
        return list(cards)
    urls = await ports.get(HELD_OBJECTS).previews(scope, held)
    return [
        card
        if card.cover is None
        else replace(
            card, cover=replace(card.cover, preview_url=urls.get(card.cover.held_object_id))
        )
        for card in cards
    ]

"""The templates of Leo's write-up a person may use (plan step 7b): shipped and their own.

Leo's layout and the eight shipped templates are listed by their cabinet codes and are
read-only (`template_builtin_read_only`). A person's own templates follow the template
rules (name, description, icon, one to four sections of distinct kinds, titles) and number
at most 50 — creates take the person's lock before they count — and a create may carry an
`Idempotency-Key`. Nothing is paid for a template: it is
only used when a write-up is written. The list is bounded — 9 shipped and at most 50 own —
so it is one page.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Final
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.idempotency.ledger import (
    EffectKey,
    EffectLedger,
    EffectScope,
    account_key,
    fingerprint_of,
)
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.features.identity.contracts import Principal
from shosai.features.meetings.application.write_up_layout import template_sections
from shosai.features.meetings.application.write_up_rewrites import TemplateNotFoundError
from shosai.features.meetings.domain.templates import (
    BUILTIN_TEMPLATES,
    LEO_LAYOUT,
    SectionKind,
    TemplateDraft,
    TemplateIcon,
    TemplateRule,
    TemplateRuleError,
    TemplateSection,
    builtin,
    checked_template,
    may_add_template,
)
from shosai.features.meetings.domain.write_up import SectionPlan, builtin_layout, own_layout
from shosai.features.meetings.infrastructure.notes_records import TemplateRecord
from shosai.features.meetings.infrastructure.template_lock import hold_template_lock

TEMPLATE_CREATES: Final = EffectScope("meetings.template_create", timedelta(hours=24))
CONFLICTS: Final = frozenset({TemplateRule.LIMIT_REACHED, TemplateRule.BUILTIN_READ_ONLY})
LEO_ICON: Final = "enhanced"


class SectionRequest(BaseModel):
    """A section as asked for: its kind and an optional title."""

    kind: SectionKind
    title: str | None = None


class TemplateRequest(BaseModel):
    """A template as asked for; its print tells a retry from another request."""

    name: str
    description: str | None
    icon: TemplateIcon
    sections: list[SectionRequest]


class TemplateMade(BaseModel):
    """The template a create made."""

    template_id: UUID


@dataclass(frozen=True, slots=True)
class Template:
    """A template as the person sees it; a shipped one has codes, not words."""

    template_id: str
    builtin: bool
    name: str | None
    description: str | None
    icon: str
    sections: tuple[SectionPlan, ...]


def rule_error(error: TemplateRuleError) -> AppError:
    """A template rule's refusal: a conflict for the limit and the shipped ones, else 422."""
    status = HTTPStatus.CONFLICT if error.rule in CONFLICTS else HTTPStatus.UNPROCESSABLE_ENTITY
    return AppError(error.code, status)


def shipped() -> list[Template]:
    """Leo's layout and the shipped templates, in the cabinet's order."""
    return [
        Template(
            template_id=template.template_id, builtin=True, name=None, description=None,
            icon=template.icon.value if template.icon is not None else LEO_ICON,
            sections=builtin_layout(template),
        )
        for template in (LEO_LAYOUT, *BUILTIN_TEMPLATES)
    ]  # fmt: skip


def own(record: TemplateRecord) -> Template:
    """A person's stored template."""
    layout = own_layout(template_sections(record.sections))
    return Template(
        template_id=str(record.id), builtin=False, name=record.name,
        description=record.description, icon=record.icon, sections=layout,
    )  # fmt: skip


def stored_sections(draft: TemplateDraft) -> list[dict[str, str | None]]:
    """A checked template's sections as the row keeps them."""
    return [{"kind": section.kind.value, "title": section.title} for section in draft.sections]


class Templates:
    """Lists the templates a person may use and keeps their own."""

    def __init__(
        self,
        transactions: HomeTransactions,
        effects: EffectLedger,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._effects = effects
        self._clock = clock

    async def every(self, principal: Principal) -> list[Template]:
        """The shipped templates, then the person's own, oldest first."""
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            records = await session.scalars(
                select(TemplateRecord)
                .where(TemplateRecord.user_id == principal.user_id)
                .order_by(TemplateRecord.created_at, TemplateRecord.id)
            )
            return [*shipped(), *(own(record) for record in records)]

    async def create(
        self, principal: Principal, request: TemplateRequest, client_key: str | None
    ) -> Template:
        """A new template of the person's; at most 50, once per key when one is sent."""
        draft = self._checked(request)
        async with self._transactions.begin(principal.scope()) as session:
            if client_key is None:
                made = await self._make(session, principal, draft)
            else:
                key = account_key(principal.user_id, client_key)
                effect = EffectKey(TEMPLATE_CREATES, key, fingerprint_of(request))
                outcome = await self._effects.once(
                    session, effect, TemplateMade, lambda: self._make(session, principal, draft)
                )
                made = outcome.outcome
            record = await self._own(session, principal, str(made.template_id))
            return own(record)

    async def replace(
        self, principal: Principal, template_id: str, request: TemplateRequest
    ) -> Template:
        """The person's template with new contents; a shipped one is read-only."""
        draft = self._checked(request)
        async with self._transactions.begin(principal.scope()) as session:
            record = await self._own(session, principal, template_id)
            record.name, record.description = draft.name, draft.description
            record.icon, record.sections = draft.icon.value, stored_sections(draft)
            record.updated_at = self._clock()
            return own(record)

    async def delete(self, principal: Principal, template_id: str) -> None:
        """Delete the person's template; meetings that used it get Leo's layout."""
        async with self._transactions.begin(principal.scope()) as session:
            await session.delete(await self._own(session, principal, template_id))

    def _checked(self, request: TemplateRequest) -> TemplateDraft:
        sections: Sequence[TemplateSection] = [
            TemplateSection(section.kind, section.title) for section in request.sections
        ]
        try:
            return checked_template(request.name, request.description, request.icon, sections)
        except TemplateRuleError as error:
            raise rule_error(error) from error

    async def _make(
        self, session: AsyncSession, principal: Principal, draft: TemplateDraft
    ) -> TemplateMade:
        await hold_template_lock(session, principal.user_id)
        count = await session.scalar(
            select(func.count())
            .select_from(TemplateRecord)
            .where(TemplateRecord.user_id == principal.user_id)
        )
        if not may_add_template(int(count or 0)):
            raise rule_error(TemplateRuleError(TemplateRule.LIMIT_REACHED))
        now = self._clock()
        record = TemplateRecord(
            id=new_id(), user_id=principal.user_id, name=draft.name,
            description=draft.description, icon=draft.icon.value,
            sections=stored_sections(draft), created_at=now, updated_at=now,
        )  # fmt: skip
        session.add(record)
        await session.flush()
        return TemplateMade(template_id=record.id)

    async def _own(
        self, session: AsyncSession, principal: Principal, template_id: str
    ) -> TemplateRecord:
        if builtin(template_id) is not None:
            raise rule_error(TemplateRuleError(TemplateRule.BUILTIN_READ_ONLY))
        try:
            record_id = UUID(template_id)
        except ValueError:
            raise TemplateNotFoundError from None
        record = await session.get(TemplateRecord, record_id, with_for_update=True)
        if record is None or record.user_id != principal.user_id:
            raise TemplateNotFoundError
        return record

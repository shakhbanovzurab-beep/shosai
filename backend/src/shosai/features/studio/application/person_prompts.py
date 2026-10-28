"""A person's prompts in Studio: written, chosen per role, their skills checked (plan §3.5).

A prompt names the person's installed skills, read through agent's `SkillReader` in the
same transaction: one the person does not have is refused, and the instructions with the
skills must fit the role's budget. A create runs once per `Idempotency-Key`, the count of
prompts checked under the person's lock. A prompt moved to another role or deleted leaves
the role it served in the same transaction, so a role never plays by a prompt of another.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.idempotency.ledger import EffectKey, EffectLedger, EffectScope
from shosai.core.kernel.ids import new_id
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.contracts import SKILL_READER
from shosai.features.identity.contracts import Principal
from shosai.features.studio.domain.errors import StudioRule, StudioRuleError
from shosai.features.studio.domain.prompts import (
    PROMPTS_MAX,
    PromptDraft,
    SkillText,
    check_budget,
    checked_draft,
)
from shosai.features.studio.domain.roles import PromptRole
from shosai.features.studio.infrastructure import prompt_store as store
from shosai.features.studio.infrastructure.person_records import PromptRecord
from shosai.features.studio.infrastructure.prompt_store import StoredPrompt

CREATE: Final = EffectScope("studio.prompt_create", timedelta(days=1))


class CreatedPrompt(BaseModel):
    """What a create stores for its retry: the prompt it wrote."""

    prompt_id: UUID


@dataclass(frozen=True, slots=True)
class PromptChanges:
    """The fields an edit replaces; none keeps the stored one."""

    name: str | None = None
    role: PromptRole | None = None
    content: str | None = None
    skill_ids: tuple[UUID, ...] | None = None


@dataclass(frozen=True, slots=True)
class PersonPromptsState:
    """The person's prompts and the prompt each role plays by."""

    prompts: tuple[StoredPrompt, ...]
    active: Mapping[PromptRole, UUID | None]


def not_found() -> StudioRuleError:
    """The answer for a prompt the person does not have."""
    return StudioRuleError(StudioRule.PROMPT_NOT_FOUND)


class PersonPrompts:
    """Lists, creates, edits and deletes a person's prompts and chooses one per role."""

    def __init__(
        self,
        transactions: HomeTransactions,
        sources: tuple[EffectLedger, PortDirectory],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._effects, self._ports = sources
        self._clock = clock

    async def state(self, principal: Principal) -> PersonPromptsState:
        """The person's prompts, the last changed first, and the active ones."""
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            return await self._state(session, principal.user_id)

    async def create(
        self, principal: Principal, draft: PromptDraft, key: EffectKey
    ) -> StoredPrompt:
        """Write a new prompt, once per key."""
        checked = checked_draft(draft)
        user_id = principal.user_id
        async with self._transactions.begin(principal.scope()) as session:

            async def effect() -> CreatedPrompt:
                await store.hold_prompts_lock(session, user_id)
                if await store.prompts_count(session, user_id) >= PROMPTS_MAX:
                    raise StudioRuleError(StudioRule.PROMPT_LIMIT_REACHED, {"max": PROMPTS_MAX})
                skills = await self._installed(session, user_id, checked.skill_ids)
                check_budget(checked.content, skills)
                prompt_id = new_id()
                session.add(
                    PromptRecord(
                        id=prompt_id, user_id=user_id, name=checked.name,
                        role=checked.role.value, content=checked.content,
                        created_at=self._clock(), updated_at=self._clock(),
                    )
                )  # fmt: skip
                await session.flush()
                await store.write_skills(session, user_id, prompt_id, checked.skill_ids)
                return CreatedPrompt(prompt_id=prompt_id)

            done = await self._effects.once(session, key, CreatedPrompt, effect)
            found = await store.prompt_of(session, user_id, done.outcome.prompt_id)
        if found is None:
            raise not_found()
        return found

    async def update(
        self, principal: Principal, prompt_id: UUID, changes: PromptChanges
    ) -> StoredPrompt:
        """Replace the given fields; a new role leaves the role the prompt served."""
        user_id = principal.user_id
        async with self._transactions.begin(principal.scope()) as session:
            record = await store.prompt_record(session, user_id, prompt_id, lock=True)
            if record is None:
                raise not_found()
            current = (await store.skills_of(session, user_id, [prompt_id])).get(prompt_id, ())
            draft = checked_draft(
                PromptDraft(
                    name=record.name if changes.name is None else changes.name,
                    role=PromptRole(record.role) if changes.role is None else changes.role,
                    content=record.content if changes.content is None else changes.content,
                    skill_ids=current if changes.skill_ids is None else changes.skill_ids,
                )
            )
            if changes.content is not None or changes.skill_ids is not None:
                check_budget(
                    draft.content, await self._installed(session, user_id, draft.skill_ids)
                )
            if draft.role.value != record.role:
                await store.release_roles(session, user_id, prompt_id)
            record.name, record.role, record.content = draft.name, draft.role.value, draft.content
            record.updated_at = self._clock()
            if changes.skill_ids is not None:
                await store.write_skills(session, user_id, prompt_id, draft.skill_ids)
            await session.flush()
            return store.stored(record, draft.skill_ids)

    async def delete(self, principal: Principal, prompt_id: UUID) -> None:
        """Delete the prompt; its skills and the role it served go with it."""
        async with self._transactions.begin(principal.scope()) as session:
            gone = await session.scalar(
                delete(PromptRecord)
                .where(PromptRecord.id == prompt_id, PromptRecord.user_id == principal.user_id)
                .returning(PromptRecord.id)
            )
        if gone is None:
            raise not_found()

    async def choose(
        self, principal: Principal, role: PromptRole, prompt_id: UUID | None
    ) -> PersonPromptsState:
        """The prompt the role plays by; none is the built-in prompt."""
        user_id = principal.user_id
        async with self._transactions.begin(principal.scope()) as session:
            if prompt_id is None:
                await store.unchoose(session, user_id, role)
            else:
                # Строка промта под блокировкой: смена роли не проскочит между проверкой и записью.
                record = await store.prompt_record(session, user_id, prompt_id, lock=True)
                if record is None:
                    raise not_found()
                if record.role != role.value:
                    raise StudioRuleError(StudioRule.PROMPT_FOR_OTHER_ROLE)
                await store.choose(session, user_id, role, prompt_id)
            return await self._state(session, user_id)

    async def _state(self, session: AsyncSession, user_id: UUID) -> PersonPromptsState:
        prompts = await store.prompts_of(session, user_id)
        return PersonPromptsState(prompts, await store.active_of(session, user_id))

    async def _installed(
        self, session: AsyncSession, user_id: UUID, skill_ids: Sequence[UUID]
    ) -> tuple[SkillText, ...]:
        """The skills in order, each one the person installed."""
        found = await self._ports.get(SKILL_READER).skills(session, user_id, skill_ids)
        missing = [skill_id for skill_id in skill_ids if skill_id not in found]
        if missing:
            raise StudioRuleError(StudioRule.SKILL_NOT_INSTALLED, {"skill_id": str(missing[0])})
        return tuple(
            SkillText(skill_id, found[skill_id].name, found[skill_id].body)
            for skill_id in skill_ids
        )

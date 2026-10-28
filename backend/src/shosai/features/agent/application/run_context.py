"""A turn's input for the model: the context builder v1 (Leo §7.3, ADR 0031; agent step 5b).

The stable head — the policy (segment 1) and the profile core (4) — opens every turn of a
thread byte for byte, so a provider's prefix cache keeps it; the tools' schemas (2) travel
beside it in the request, in a fixed order (step 6), and a skill (3) joins it with its step.
Then the thread's summary (5), the newest questions and answers before the question that fit
5 000 tokens, oldest first (6) — a failed answer's text is left out, a regenerated question's
earlier answers too, and earlier turns' tool rounds always; a decided card is a server note
in registered words — and last the volatile part (7: the time to the minute in the person's
zone, the page and what it shows) with the question (8); a page's subject someone else wrote
taints the run like a tool's result. The thread and the run are read as the person: a deleted
thread ends the run before the model is asked, and so does a run the sweep ended while it
waited for a worker.
"""

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

from sqlalchemy import or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.provenance import Provenance
from shosai.core.ai.requests import ChatMessage, ChatRequest, Role, TextPart
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.attachment_notes import attachments_block
from shosai.features.agent.application.context_parts import cap, person_of, zone_info
from shosai.features.agent.application.history_text import said
from shosai.features.agent.application.memory_context import MemoryContext, Recalling
from shosai.features.agent.application.profile_segment import profile_segment
from shosai.features.agent.application.studio_context import platform_layer
from shosai.features.agent.application.surface_digest import Subject, subject_digest
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.domain.budgets import (
    Segment,
    estimate_tokens,
    recent_window,
)
from shosai.features.agent.domain.context import clean_path, clip, now_line, page_line
from shosai.features.agent.domain.memory_text import MemoryBlock
from shosai.features.agent.domain.operator import is_operator
from shosai.features.agent.domain.runs import RunStatus
from shosai.features.agent.domain.threads import AnswerStatus, MessageRole
from shosai.features.agent.domain.wrapper import BOUNDARY_BYTES, boundary
from shosai.features.agent.infrastructure.profile_key import KEY_BYTES
from shosai.features.agent.infrastructure.prompts import (
    OPERATOR_POLICY,
    POLICY,
    QUESTION,
    SUMMARY,
    VOLATILE,
)
from shosai.features.agent.infrastructure.run_records import AgentRunRecord
from shosai.features.agent.infrastructure.thread_records import (
    SPOKEN,
    AgentMessageRecord,
    AgentThreadRecord,
)

MESSAGE = AgentMessageRecord
MAX_OUTPUT_TOKENS: Final = 4_096
# Строк читается с запасом: окно режет их по токенам, редкий тред упрётся в это число раньше.
HISTORY_ROWS: Final = 60
# Заметка сервера о решении по карточке читается моделью как сообщение-примечание Shosai.
ROLES: Final = {
    MessageRole.USER.value: Role.USER,
    MessageRole.ASSISTANT.value: Role.ASSISTANT,
    MessageRole.SERVER.value: Role.USER,
}


class ThreadGoneError(Exception):
    """The run's thread was deleted after the turn was admitted."""


class RunOverError(Exception):
    """The run ended before its worker took it: the sweep found it lost meanwhile."""


def text_message(role: Role, text: str) -> ChatMessage:
    """One message of plain text."""
    return ChatMessage(role=role, parts=(TextPart(text),))


def text_of(message: ChatMessage) -> str:
    """The text of a message of plain text."""
    return "".join(part.text for part in message.parts if isinstance(part, TextPart))


@dataclass(frozen=True, slots=True)
class PreparedContext:
    """A context read in its transaction, and the recall still on its way."""

    head: str
    history: list[ChatMessage]
    volatile: str
    asked: str
    recalling: Recalling | None


class ContextBuilder:
    """Builds the model's input of a run, as the person."""

    def __init__(
        self,
        ports: PortDirectory,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        memory: MemoryContext | None = None,
    ) -> None:
        self._ports = ports
        self._clock = clock
        self.memory = memory or MemoryContext(ports, secrets.token_bytes(KEY_BYTES))

    async def request(
        self,
        session: AsyncSession,
        payload: TurnPayload,
        sizes: dict[Segment, int] | None = None,
        labels: list[tuple[Provenance, str]] | None = None,
    ) -> ChatRequest:
        """The request for the model, read in the person's transaction; `sizes` receives the
        segments' estimated tokens, `labels` each wrapped text the context holds, labelled."""
        return self.build(await self.prepare(session, payload, sizes, labels))

    async def prepare(
        self,
        session: AsyncSession,
        payload: TurnPayload,
        sizes: dict[Segment, int] | None = None,
        labels: list[tuple[Provenance, str]] | None = None,
        *,
        recall: bool = False,
    ) -> PreparedContext:
        """The context's parts, read in the person's transaction; with `recall`, memory starts
        recalling for the question beside the rest, to be awaited after the transaction."""
        user_id = person_of(payload)
        thread, question = await self._turn(session, payload, user_id)
        core, zone, remembered = await profile_segment((self._ports, self.memory), session, payload)
        if labels is not None:
            labels.extend(remembered.tainting)
        # Сводка идёт после стабильной головы: кэш провайдера держит голову целиком.
        summary = SUMMARY.format(summary=clip(thread.summary, cap(5))) if thread.summary else ""
        policy = OPERATOR_POLICY if is_operator(user_id) else POLICY
        layer = await platform_layer(self._ports, user_id)
        head = "\n\n".join(part for part in (policy, layer, core, summary) if part)
        token = boundary(secrets.token_bytes(BOUNDARY_BYTES))
        history = await self._recent(session, thread, question, token)
        earlier = next((text_of(m) for m in reversed(history) if m.role is Role.ASSISTANT), "")
        recall = recall and remembered.on
        recalling = self.memory.recall(payload, question.text, earlier) if recall else None
        volatile = await self._volatile(session, payload, zone, labels)
        attached = attachments_block(question.digest, token)
        if attached is not None and labels is not None:
            labels.append((Provenance.FILE_OWN, attached))
        asked = QUESTION.format(text=question.text)
        asked = asked if attached is None else f"{asked}\n\n{attached}"
        if sizes is not None:
            sizes |= {
                Segment.POLICY: estimate_tokens(policy) + estimate_tokens(layer),
                Segment.PROFILE: estimate_tokens(core),
                Segment.SUMMARY: estimate_tokens(summary),
                Segment.RECENT: sum(estimate_tokens(text_of(message)) for message in history),
                Segment.VOLATILE: estimate_tokens(volatile),
                Segment.QUESTION: estimate_tokens(asked),
            }
        return PreparedContext(head, history, volatile, asked, recalling)

    @staticmethod
    def build(prepared: PreparedContext, recalled: MemoryBlock | None = None) -> ChatRequest:
        """The request from its parts, the recalled facts before the question."""
        middle = recalled.text if recalled is not None else ""
        last = "\n\n".join(part for part in (prepared.volatile, middle, prepared.asked) if part)
        return ChatRequest(
            messages=(
                text_message(Role.SYSTEM, prepared.head),
                *prepared.history,
                text_message(Role.USER, last),
            ),
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )

    async def _turn(
        self, session: AsyncSession, payload: TurnPayload, user_id: UUID
    ) -> tuple[AgentThreadRecord, AgentMessageRecord]:
        """The run's thread and question, read as the person; an ended run or a deleted thread
        ends the turn before the model is asked."""
        status = await session.scalar(
            select(AgentRunRecord.status).where(
                AgentRunRecord.id == payload.run_id,
                AgentRunRecord.started_at == payload.started_at,
            )
        )
        if status != RunStatus.RUNNING.value:
            raise RunOverError
        thread = await session.scalar(
            select(AgentThreadRecord).where(
                AgentThreadRecord.id == payload.thread_id, AgentThreadRecord.user_id == user_id
            )
        )
        if thread is None:
            raise ThreadGoneError
        question = await session.scalar(
            select(MESSAGE).where(
                MESSAGE.id == payload.question_id,
                MESSAGE.thread_id == thread.id,
                MESSAGE.created_at >= thread.created_at,
            )
        )
        if question is None:
            raise ThreadGoneError
        return thread, question

    async def _recent(
        self,
        session: AsyncSession,
        thread: AgentThreadRecord,
        question: AgentMessageRecord,
        token: str,
    ) -> list[ChatMessage]:
        """Segment 6: the newest messages before the question and after the summary."""
        since = thread.created_at
        if thread.summary_upto is not None:
            folded = await session.scalar(
                select(MESSAGE.created_at).where(
                    MESSAGE.id == thread.summary_upto, MESSAGE.thread_id == thread.id
                )
            )
            since = folded or since
        position = tuple_(MESSAGE.created_at, MESSAGE.id)
        conditions = [
            MESSAGE.thread_id == thread.id,
            MESSAGE.user_id == thread.user_id,
            MESSAGE.created_at >= since,
            position < tuple_(question.created_at, question.id),
            MESSAGE.role.in_(tuple(ROLES)),
            or_(MESSAGE.status.is_(None), MESSAGE.status != AnswerStatus.FAILED.value),
            SPOKEN,
        ]
        if thread.summary_upto is not None:
            conditions.append(MESSAGE.id != thread.summary_upto)
        rows = (
            await session.execute(
                select(
                    MESSAGE.id,
                    MESSAGE.role,
                    MESSAGE.text,
                    MESSAGE.tokens,
                    MESSAGE.sources,
                    MESSAGE.digest,
                )
                .where(*conditions)
                .order_by(MESSAGE.created_at.desc(), MESSAGE.id.desc())
                .limit(HISTORY_ROWS)
            )
        ).all()
        texts = [said(row.role, row.text, row.digest, row.sources, token) for row in rows]
        sizes = [row.tokens + estimate_tokens(text) - estimate_tokens(row.text)
                 for row, text in zip(rows, texts, strict=True)]  # fmt: skip
        kept = recent_window(sizes, cap(6))
        return [text_message(ROLES[rows[i].role], texts[i]) for i in reversed(range(kept))]

    async def _volatile(
        self,
        session: AsyncSession,
        payload: TurnPayload,
        zone: str,
        labels: list[tuple[Provenance, str]] | None,
    ) -> str:
        """Segment 7: the time to the minute, the page and what it shows."""
        lines = [now_line(self._clock().astimezone(zone_info(zone)), zone)]
        path = clean_path(payload.path)
        if path is not None:
            lines.append(page_line(path))
        if payload.subject_kind is not None and payload.subject_id is not None:
            subject = Subject(payload.subject_kind, payload.subject_id)
            token = boundary(secrets.token_bytes(BOUNDARY_BYTES))
            digest = await subject_digest(
                session, self._ports, (person_of(payload), subject), token
            )
            if digest is not None:
                lines.append(digest.text)
                if digest.label is not None and labels is not None:
                    labels.append((digest.label, digest.text))
        return VOLATILE.format(context=clip("\n".join(lines), cap(7)))

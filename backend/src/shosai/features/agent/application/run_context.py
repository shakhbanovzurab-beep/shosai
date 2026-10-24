"""A turn's input for the model: the context builder v1 (Leo §7.3, ADR 0031; agent step 5b).

The stable head — the policy (segment 1) and the profile core (4) — opens every turn of a
thread byte for byte, so a provider's prefix cache keeps it; the tools' schemas (2) travel
beside it in the request, in a fixed order (step 6), and a skill (3) joins it with its step.
Then the thread's summary (5), the newest questions and answers before the question that fit
5 000 tokens, oldest first (6) — a failed answer's text is left out, a regenerated question's
earlier answers too, and earlier turns' tool rounds always — and last the volatile part (7:
the time to the minute in the person's zone, the page and what it shows) with the question
(8). The thread and the run are read as the person: a deleted thread ends the run before the
model is asked, and so does a run the sweep ended while it waited for a worker.
"""

import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.requests import ChatMessage, ChatRequest, Role, TextPart
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.surface_digest import Subject, subject_digest
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.domain.budgets import (
    SEGMENT_CAPS,
    Segment,
    estimate_tokens,
    recent_window,
)
from shosai.features.agent.domain.context import clean_path, clip, now_line, page_line, profile_core
from shosai.features.agent.domain.runs import RunStatus
from shosai.features.agent.domain.threads import AnswerStatus, MessageRole
from shosai.features.agent.domain.wrapper import BOUNDARY_BYTES, boundary
from shosai.features.agent.infrastructure.prompts import (
    POLICY,
    QUESTION,
    SUMMARY,
    VOLATILE,
    turn_instructions,
)
from shosai.features.agent.infrastructure.run_records import AgentRunRecord
from shosai.features.agent.infrastructure.thread_records import (
    SPOKEN,
    AgentMessageRecord,
    AgentThreadRecord,
)
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER

MESSAGE = AgentMessageRecord
MAX_OUTPUT_TOKENS: Final = 4_096
# Строк читается с запасом: окно режет их по токенам, редкий тред упрётся в это число раньше.
HISTORY_ROWS: Final = 60
ROLES: Final = {MessageRole.USER.value: Role.USER, MessageRole.ASSISTANT.value: Role.ASSISTANT}
UTC_ZONE: Final = "UTC"


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


class ContextBuilder:
    """Builds the model's input of a run, as the person."""

    def __init__(
        self, ports: PortDirectory, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        self._ports = ports
        self._clock = clock

    async def request(
        self,
        session: AsyncSession,
        payload: TurnPayload,
        sizes: dict[Segment, int] | None = None,
    ) -> ChatRequest:
        """The request for the model, read in the person's transaction; `sizes` receives the
        segments' estimated tokens."""
        user_id = person_of(payload)
        await self._still_running(session, payload)
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
        profile = await self._ports.get(ACCOUNT_PROFILE_READER).profile(session, user_id)
        zone = profile.timezone if profile is not None and profile.timezone else UTC_ZONE
        core = profile_core(
            profile.display_name if profile is not None else "",
            zone,
            turn_instructions(payload.language, payload.length),
        )
        # Сводка идёт после стабильной головы: кэш провайдера держит голову целиком.
        summary = SUMMARY.format(summary=clip(thread.summary, cap(5))) if thread.summary else ""
        head = "\n\n".join(part for part in (POLICY, core, summary) if part)
        history = await self._recent(session, thread, question)
        volatile = await self._volatile(session, payload, zone)
        if sizes is not None:
            sizes |= {
                Segment.POLICY: estimate_tokens(POLICY),
                Segment.PROFILE: estimate_tokens(core),
                Segment.SUMMARY: estimate_tokens(summary),
                Segment.RECENT: sum(estimate_tokens(text_of(message)) for message in history),
                Segment.VOLATILE: estimate_tokens(volatile),
                Segment.QUESTION: estimate_tokens(question.text),
            }
        return ChatRequest(
            messages=(
                text_message(Role.SYSTEM, head),
                *history,
                text_message(Role.USER, f"{volatile}\n\n{QUESTION.format(text=question.text)}"),
            ),
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )

    async def _still_running(self, session: AsyncSession, payload: TurnPayload) -> None:
        status = await session.scalar(
            select(AgentRunRecord.status).where(
                AgentRunRecord.id == payload.run_id,
                AgentRunRecord.started_at == payload.started_at,
            )
        )
        if status != RunStatus.RUNNING.value:
            raise RunOverError

    async def _recent(
        self, session: AsyncSession, thread: AgentThreadRecord, question: AgentMessageRecord
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
                select(MESSAGE.id, MESSAGE.role, MESSAGE.text, MESSAGE.tokens)
                .where(*conditions)
                .order_by(MESSAGE.created_at.desc(), MESSAGE.id.desc())
                .limit(HISTORY_ROWS)
            )
        ).all()
        kept = rows[: recent_window([row.tokens for row in rows], cap(6))]
        return [text_message(ROLES[row.role], row.text) for row in reversed(kept)]

    async def _volatile(self, session: AsyncSession, payload: TurnPayload, zone: str) -> str:
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
        return VOLATILE.format(context=clip("\n".join(lines), cap(7)))


def cap(segment: int) -> int:
    """A segment's cap in tokens, by its number in Leo §7.3."""
    return SEGMENT_CAPS[list(Segment)[segment - 1]]


def zone_info(zone: str) -> ZoneInfo:
    """The zone the person's profile names, UTC for one the system does not know."""
    try:
        return ZoneInfo(zone)
    except ZoneInfoNotFoundError, ValueError:
        return ZoneInfo(UTC_ZONE)


def person_of(payload: TurnPayload) -> UUID:
    """The person a run acts for."""
    if payload.user_id is None:
        message = "ход Leo идёт от имени человека"
        raise ValueError(message)
    return payload.user_id

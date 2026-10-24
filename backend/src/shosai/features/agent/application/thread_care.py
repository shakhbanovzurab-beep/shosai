"""A thread's title and summary, written by the utility model after a turn (Leo §7.3; step 5b).

The title: after the first answer, while the person has not renamed the thread, a few words in
the language of the person's first message replace the question's first line. The summary:
when the messages not yet folded pass 70 % of the recent segment's cap, the oldest of them —
all but the newest 2 500 tokens — are folded into the summary, which always opens with the
thread's first question, so a long thread never loses what it was about. The model reads the
conversation between markers, as text to summarise and never as instructions. Each write is
conditional on what it read: a rename or another compaction meanwhile wins, and a repeat
changes nothing. A model that fails leaves the thread as it was, logged.
"""

import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Protocol
from uuid import UUID

import structlog
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.spec import Provenance
from shosai.core.ai.calls import CallClass, CallContext, CallOrigin, ModelRoute
from shosai.core.ai.errors import AiCallError
from shosai.core.ai.requests import ChatMessage, ChatRequest, Role, TextPart
from shosai.core.ai.results import ChatResult
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.after_turn import QUESTION_TITLE, ThreadTask
from shosai.features.agent.domain.budgets import SEGMENT_CAPS, Segment, needs_compaction
from shosai.features.agent.domain.context import clip
from shosai.features.agent.domain.threads import (
    AnswerStatus,
    MessageRole,
    ThreadRuleError,
    clean_title,
)
from shosai.features.agent.domain.wrapper import BOUNDARY_BYTES, Label, boundary, wrap
from shosai.features.agent.infrastructure.prompts import FIRST_QUESTION, SUMMARY_TASK, TITLE_TASK
from shosai.features.agent.infrastructure.thread_records import (
    SPOKEN,
    AgentMessageRecord,
    AgentThreadRecord,
)
from shosai.features.identity.contracts import CONSENT_READER

MESSAGE = AgentMessageRecord
THREAD = AgentThreadRecord
KEEP_TOKENS: Final = 2_500
FIRST_TOKENS: Final = 300
FOLD_TOKENS: Final = 12_000
TITLE_TOKENS: Final = 32
SUMMARY_TOKENS: Final = 900
SPEAKERS: Final = {MessageRole.USER.value: "Person", MessageRole.ASSISTANT.value: "Leo"}
# Кавычки и точки, которыми модель любит обрамлять заголовок.
TITLE_TRIM: Final = "\"'«»“”„.!"
log = structlog.stdlib.get_logger(__name__)


class ChatModel(Protocol):
    """The provider port's chat, as the thread's care uses it."""

    async def chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> ChatResult:
        """The model's whole answer."""
        ...


@dataclass(frozen=True, slots=True)
class Line:
    """A message of the conversation as the summary reads it."""

    message_id: UUID
    role: str
    text: str
    tokens: int


class ThreadCare:
    """Titles and summaries of the person's threads."""

    def __init__(
        self,
        transactions: HomeTransactions,
        model: tuple[ChatModel, ModelRoute | None],
        ports: PortDirectory,
    ) -> None:
        self._transactions = transactions
        self._ai, self._route = model
        self._ports = ports

    async def title(self, task: ThreadTask) -> None:
        """Name a thread after its first answer, unless the person renamed it."""
        async with self._transactions.begin(task.scope(), read_only=True) as session:
            thread = await session.get(THREAD, task.thread_id)
            if thread is None or thread.title_source != QUESTION_TITLE:
                return
            first = await opening(session, thread)
            consent = await self._consent(session, task)
        if len(first) < 2 or self._route is None:
            return
        transcript = "\n\n".join(
            f"{SPEAKERS[line.role]}: {clip(line.text, FOLD_TOKENS // 4)}" for line in first
        )
        answer = await self._ask(
            (task, f"title:{task.thread_id}"), (TITLE_TASK, transcript), (TITLE_TOKENS, consent)
        )
        if answer is None:
            return
        try:
            title = clean_title(answer.strip().strip(TITLE_TRIM))
        except ThreadRuleError:
            log.warning("Модель не дала заголовок треда Leo", thread_id=str(task.thread_id))
            return
        async with self._transactions.begin(task.scope()) as session:
            await session.execute(
                update(THREAD)
                .where(THREAD.id == task.thread_id, THREAD.title_source == QUESTION_TITLE)
                .values(title=title, title_source="model")
            )

    async def compact(self, task: ThreadTask) -> None:
        """Fold the oldest unfolded messages into the thread's summary."""
        async with self._transactions.begin(task.scope(), read_only=True) as session:
            thread = await session.get(THREAD, task.thread_id)
            if thread is None:
                return
            lines = await unfolded(session, thread)
            question = (await opening(session, thread))[:1]
            consent = await self._consent(session, task)
            summary, upto = thread.summary, thread.summary_upto
        fold = to_fold(lines)
        if not fold or not question or self._route is None:
            return
        token = boundary(secrets.token_bytes(BOUNDARY_BYTES))
        earlier = f"{summary}\n\n" if summary else ""
        transcript = earlier + "\n\n".join(f"{SPEAKERS[line.role]}: {line.text}" for line in fold)
        wrapped = wrap(clip(transcript, FOLD_TOKENS), Label.of(Provenance.MEMORY), token)
        written = await self._ask(
            (task, f"compaction:{task.thread_id}:{fold[-1].message_id}"),
            (SUMMARY_TASK, wrapped),
            (SUMMARY_TOKENS, consent),
        )
        if written is None:
            return
        head = FIRST_QUESTION.format(question=clip(question[0].text, FIRST_TOKENS))
        folded = clip(f"{head}\n\n{written.strip()}", SEGMENT_CAPS[Segment.SUMMARY])
        async with self._transactions.begin(task.scope()) as session:
            unchanged = (
                THREAD.summary_upto.is_(None) if upto is None else THREAD.summary_upto == upto
            )
            await session.execute(
                update(THREAD)
                .where(THREAD.id == task.thread_id, unchanged)
                .values(summary=folded, summary_upto=fold[-1].message_id)
            )

    async def _consent(self, session: AsyncSession, task: ThreadTask) -> bool:
        if task.user_id is None:
            return False
        return await self._ports.get(CONSENT_READER).cross_border(session, task.user_id)

    async def _ask(
        self,
        keyed: tuple[ThreadTask, str],
        prompt: tuple[str, str],
        limits: tuple[int, bool],
    ) -> str | None:
        """The utility model's answer, or None when it failed (logged). The call's key names
        its effect — a thread's title, a fold up to a message — so a repeat is recorded once."""
        task, effect = keyed
        instruction, content = prompt
        output, consent = limits
        if self._route is None or task.user_id is None:
            return None
        purpose = effect.split(":", 1)[0]
        context = CallContext(
            effect_key=f"agent.{effect}",
            feature=f"agent.{purpose}",
            call_class=CallClass.STANDARD,
            origin=CallOrigin.BACKGROUND,
            scope=task.scope(),
            cross_border_consent=consent or task.home is Home.EU,
        )
        request = ChatRequest(
            messages=(
                ChatMessage(role=Role.SYSTEM, parts=(TextPart(instruction),)),
                ChatMessage(role=Role.USER, parts=(TextPart(content),)),
            ),
            max_output_tokens=output,
        )
        try:
            return (await self._ai.chat(context, self._route, request)).text
        except AiCallError as error:
            log.warning("Модель не помогла треду Leo", purpose=purpose, failure=error.failure.value)
            return None


async def opening(session: AsyncSession, thread: AgentThreadRecord) -> list[Line]:
    """The thread's first question and its first answer."""
    rows = (
        await session.execute(
            select(MESSAGE.id, MESSAGE.role, MESSAGE.text, MESSAGE.tokens)
            .where(
                MESSAGE.thread_id == thread.id,
                MESSAGE.created_at >= thread.created_at,
                MESSAGE.role.in_(tuple(SPEAKERS)),
                SPOKEN,
            )
            .order_by(MESSAGE.created_at, MESSAGE.id)
            .limit(2)
        )
    ).all()
    return [Line(*row) for row in rows]


async def unfolded(session: AsyncSession, thread: AgentThreadRecord) -> list[Line]:
    """The messages the summary has not folded, oldest first, without failed answers."""
    since = thread.created_at
    if thread.summary_upto is not None:
        folded = await session.scalar(
            select(MESSAGE.created_at).where(
                MESSAGE.id == thread.summary_upto, MESSAGE.thread_id == thread.id
            )
        )
        since = folded or since
    conditions = [
        MESSAGE.thread_id == thread.id,
        MESSAGE.created_at >= since,
        MESSAGE.role.in_(tuple(SPEAKERS)),
        or_(MESSAGE.status.is_(None), MESSAGE.status != AnswerStatus.FAILED.value),
        SPOKEN,
    ]
    if thread.summary_upto is not None:
        conditions.append(MESSAGE.id != thread.summary_upto)
    rows = (
        await session.execute(
            select(MESSAGE.id, MESSAGE.role, MESSAGE.text, MESSAGE.tokens)
            .where(*conditions)
            .order_by(MESSAGE.created_at, MESSAGE.id)
        )
    ).all()
    return [Line(*row) for row in rows]


def to_fold(lines: Sequence[Line]) -> list[Line]:
    """The oldest lines past the newest 2 500 tokens, when the whole passes 70 % of the cap."""
    if not needs_compaction(sum(line.tokens for line in lines)):
        return []
    kept, total = len(lines), 0
    while kept > 0 and total + lines[kept - 1].tokens <= KEEP_TOKENS:
        kept -= 1
        total += lines[kept].tokens
    return list(lines[:kept])

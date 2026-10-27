"""The person's own words of a turn, for memory's admission (memory plan §3.2, ADR 0071).

Memory reads the question of a finished run as the person wrote or said it, the run's final
taint, the thread's space, and — for references only — the two exchanges before it, the
answers cut to their opening. Never a tool round, an attachment, a server note or the
operator's turn: a run that did not end with an answer, or a thread gone meanwhile, gives
nothing.
"""

from typing import Final
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.context import Taint
from shosai.features.agent.contracts.memory import PriorExchange, TurnWords
from shosai.features.agent.domain.operator import is_operator
from shosai.features.agent.domain.runs import RunStatus
from shosai.features.agent.domain.threads import AnswerStatus, MessageRole
from shosai.features.agent.infrastructure.run_records import AgentRunRecord
from shosai.features.agent.infrastructure.thread_records import (
    SPOKEN,
    AgentMessageRecord,
    AgentThreadRecord,
)

MESSAGE = AgentMessageRecord
EXCHANGES: Final = 2
ANSWER_HEAD: Final = 300


class AgentPersonWords:
    """The `agent.person_words` binding."""

    async def of_turn(self, session: AsyncSession, user_id: UUID, run_id: UUID) -> TurnWords | None:
        """The run's question and what came just before it."""
        if is_operator(user_id):
            return None
        run = await session.scalar(
            select(AgentRunRecord).where(
                AgentRunRecord.id == run_id, AgentRunRecord.user_id == user_id
            )
        )
        if run is None or run.status != RunStatus.COMPLETED.value:
            return None
        thread = await session.get(AgentThreadRecord, run.thread_id)
        question = await session.scalar(
            select(MESSAGE).where(
                MESSAGE.run_id == run_id,
                MESSAGE.thread_id == run.thread_id,
                MESSAGE.role == MessageRole.USER.value,
            )
        )
        if thread is None or thread.user_id != user_id or question is None:
            return None
        before = await self._before(session, question)
        return TurnWords(
            thread_id=thread.id,
            message_id=question.id,
            org_id=thread.org_id,
            text=question.text,
            taint=Taint(run.taint),
            said_at=question.created_at,
            before=before,
        )

    @staticmethod
    async def _before(
        session: AsyncSession, question: AgentMessageRecord
    ) -> tuple[PriorExchange, ...]:
        """The exchanges before the question, oldest first, answers cut to their opening."""
        rows = (
            await session.execute(
                select(MESSAGE.role, MESSAGE.text)
                .where(
                    MESSAGE.thread_id == question.thread_id,
                    MESSAGE.created_at < question.created_at,
                    MESSAGE.role.in_((MessageRole.USER.value, MessageRole.ASSISTANT.value)),
                    (MESSAGE.status.is_(None)) | (MESSAGE.status == AnswerStatus.DONE.value),
                    SPOKEN,
                )
                .order_by(MESSAGE.created_at.desc())
                .limit(EXCHANGES * 2)
            )
        ).all()
        exchanges: list[PriorExchange] = []
        answer = ""
        for role, text in rows:
            if role == MessageRole.ASSISTANT.value:
                answer = text[:ANSWER_HEAD]
            else:
                exchanges.append(PriorExchange(question=text, answer_head=answer))
                answer = ""
        return tuple(reversed(exchanges))

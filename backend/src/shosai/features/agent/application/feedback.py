"""A person's rating of Leo's answer, and the evaluation case it may make (ADR 0068 AG-D13;
step 11a).

`PUT` rates one of the person's answers in a thread they still see; the same rating again is
answered as it stands. Each rating is the moment the case rule is read: with the person's
`improve_models` consent and no source in a workspace, the turn is kept as a case — one per
answer, its rating following the rating — and without them any case of the answer goes. `DELETE`
removes the rating, and its case with it. A question, a note, another person's answer or a
hidden thread is `message_not_found`.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.eval_cases import PROMPT_VERSION, case_copy
from shosai.features.agent.application.threads import Threads
from shosai.features.agent.domain.feedback import Rating, case_allowed
from shosai.features.agent.domain.runs import Channel
from shosai.features.agent.domain.threads import MessageRole
from shosai.features.agent.infrastructure.feedback_metrics import FeedbackMetrics, RatedTurn
from shosai.features.agent.infrastructure.person_records import (
    AgentEvalCaseRecord,
    AgentFeedbackRecord,
)
from shosai.features.agent.infrastructure.run_records import AgentRunRecord
from shosai.features.agent.infrastructure.thread_records import AgentMessageRecord
from shosai.features.identity.contracts import CONSENT_READER, Principal

FEEDBACK = AgentFeedbackRecord
CASE = AgentEvalCaseRecord
MESSAGE = AgentMessageRecord


@dataclass(frozen=True, slots=True)
class FeedbackView:
    """The rating and whether the turn became an evaluation case."""

    rating: Rating
    shared: bool


def message_not_found() -> AppError:
    """No answer of the person by that id."""
    return AppError("message_not_found", HTTPStatus.NOT_FOUND)


def _spaces(answer: AgentMessageRecord) -> list[UUID | None]:
    """The workspaces of the answer's sources, None for the person's own."""
    return [
        UUID(str(source["org_id"])) if source.get("org_id") else None for source in answer.sources
    ]


class Feedback:
    """Rates answers and keeps the cases the rule allows."""

    def __init__(
        self,
        parts: tuple[HomeTransactions, PortDirectory, Threads],
        metrics: FeedbackMetrics,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions, self._ports, self._threads = parts
        self._metrics = metrics
        self._clock = clock

    async def rate(self, principal: Principal, message_id: UUID, rating: Rating) -> FeedbackView:
        """Rate the answer; the case follows the rule as it reads now."""
        now = self._clock()
        async with self._transactions.begin(principal.scope()) as session:
            answer = await self._answer(session, principal, message_id)
            before = await session.scalar(
                select(FEEDBACK.rating).where(FEEDBACK.message_id == answer.id).with_for_update()
            )
            # Случай ссылается на оценку: её строка пишется первой, флаг — после правила.
            await session.execute(
                insert(FEEDBACK)
                .values(
                    message_id=answer.id,
                    user_id=principal.user_id,
                    thread_id=answer.thread_id,
                    run_id=answer.run_id,
                    rating=rating.value,
                    updated_at=now,
                )
                .on_conflict_do_update(
                    index_elements=[FEEDBACK.message_id],
                    set_={"rating": rating.value, "updated_at": now},
                )
            )
            shared = await self._case(session, answer, rating)
            await session.execute(
                update(FEEDBACK).where(FEEDBACK.message_id == answer.id).values(shared=shared)
            )
            turn = await self._turn(session, answer)
        if before != rating.value:
            self._metrics.rated(rating, turn)
        return FeedbackView(rating, shared)

    async def remove(self, principal: Principal, message_id: UUID) -> None:
        """Take the rating back, and its case with it."""
        async with self._transactions.begin(principal.scope()) as session:
            answer = await self._answer(session, principal, message_id)
            await session.execute(delete(FEEDBACK).where(FEEDBACK.message_id == answer.id))

    async def _answer(
        self, session: AsyncSession, principal: Principal, message_id: UUID
    ) -> AgentMessageRecord:
        """The person's answer in a thread they still see, locked against a second rating."""
        answer = await session.scalar(
            select(MESSAGE)
            .where(
                MESSAGE.id == message_id,
                MESSAGE.user_id == principal.user_id,
                MESSAGE.role == MessageRole.ASSISTANT.value,
                MESSAGE.tool_calls.is_(None),
                MESSAGE.run_id.is_not(None),
            )
            # Две оценки одного ответа идут по очереди: случай ответа — один.
            .with_for_update()
        )
        if answer is None:
            raise message_not_found()
        try:
            await self._threads.visible_thread(session, principal.user_id, answer.thread_id)
        except AppError as error:
            raise message_not_found() from error
        return answer

    async def _case(
        self, session: AsyncSession, answer: AgentMessageRecord, rating: Rating
    ) -> bool:
        """Keep, re-rate or drop the answer's case by the rule; whether one is kept."""
        consent = await self._ports.get(CONSENT_READER).improve_models(session, answer.user_id)
        if not case_allowed(_spaces(answer), consent_given=consent):
            await session.execute(delete(CASE).where(CASE.message_id == answer.id))
            return False
        known = await session.scalar(select(CASE).where(CASE.message_id == answer.id))
        if known is not None:
            known.rating = rating.value
            return True
        copy = await case_copy(session, self._ports, answer)
        session.add(
            CASE(
                id=new_id(), user_id=answer.user_id, message_id=answer.id,
                thread_id=answer.thread_id, rating=rating.value, language=copy.language,
                case=copy.case, model=copy.model, tier=copy.tier, toolsets=copy.toolsets,
                prompt_version=PROMPT_VERSION,
            )
        )  # fmt: skip
        return True

    async def _turn(self, session: AsyncSession, answer: AgentMessageRecord) -> RatedTurn:
        """What made the answer, as the counters' labels."""
        run = await session.scalar(select(AgentRunRecord).where(AgentRunRecord.id == answer.run_id))
        if run is None:
            return RatedTurn(None, None, Channel.WEB.value, None, ())
        routing = run.routing or {}
        toolsets = [*routing.get("selected", []), *routing.get("loaded", [])]
        return RatedTurn(run.model, run.tier, run.channel, run.language, [str(t) for t in toolsets])

"""A turn admitted, committed and sent to an agent worker (Leo §5.2 steps 1 to 5, ADR 0068 AG-D12).

A turn is one `Idempotency-Key`: the same key again answers the run it made, before any limit
is counted. A new one is refused before anything is written when the person in the Russian
home has not consented to cross-border transfer (403 `consent_required`), when their plan's
tokens are spent (402 `token_limit`), past 20 turns a minute (429 `rate_limited`), with two
runs already going (429 `too_many_runs`), or when the agent workers are full (429
`agent_busy`). It then takes its thread's lease — a busy thread is 409 `thread_busy` unless
the turn supersedes the running one, which is asked to stop first — and commits its question
and its run in one transaction. `run.started` is written to the run's log before the task is
sent, so the stream has its first event the moment it opens. What an admission took is given
back on every failure after it; a Valkey that does not answer is 503 `agent_unavailable`. The
platform operator's turn (AG-D5) has no plan to ask and no consent to give: the platform pays
it, it is answered in Russian and carries no attachments (422 `attachments_not_allowed`). The
switches the person left on travel with the turn, memory's among them while it is on.
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Final
from uuid import UUID

import structlog
from pydantic import BaseModel

from shosai.core.idempotency.ledger import (
    EffectKey,
    EffectScope,
    account_key,
    fingerprint_of,
)
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.kv.rate_limits import RateLimit
from shosai.core.tasks.errors import TaskQueueUnavailableError
from shosai.core.web.rate_limit import RateLimitedError
from shosai.features.agent.application.memory_context import memory_switches
from shosai.features.agent.application.preferences import preferences_of
from shosai.features.agent.application.surface_digest import Subject
from shosai.features.agent.application.token_admission import standard_tokens
from shosai.features.agent.application.turn_commit import (
    TurnMade,
    TurnParts,
    abandon_turn,
    commit_turn,
)
from shosai.features.agent.application.turn_task import RUN_TURN, TurnPayload, started_event
from shosai.features.agent.domain.operator import OPERATOR_LANGUAGE, is_operator
from shosai.features.agent.domain.preferences import Switch, answer_language
from shosai.features.agent.domain.threads import ThreadRuleError, TurnKind, check_question
from shosai.features.agent.infrastructure.fleet import Admission
from shosai.features.agent.infrastructure.person_records import AgentSettingsRecord
from shosai.features.billing.contracts import TokenRoute
from shosai.features.identity.contracts import CONSENT_READER, Principal

TURN_LIMIT: Final = RateLimit("agent.turn", 20, timedelta(minutes=1), 5)
# Маршрут токенов хода оператора: в пределах — тарифа нет, расход несёт платформенный счёт.
OPERATOR_ROUTE: Final = TokenRoute.WITHIN_ALLOWANCE.value
TURN_KEYS: Final = EffectScope("agent.turn", timedelta(hours=24))
SUPERSEDE_WAIT: Final = timedelta(seconds=5)
SUPERSEDE_POLL: Final = timedelta(milliseconds=100)
# Через сколько секунд предлагать повтор, когда заняты ходы человека или воркеры.
BUSY_RETRY_SECONDS: Final = 5
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Page:
    """The cabinet page the person is on and what it shows."""

    path: str | None
    subject: Subject | None


@dataclass(frozen=True, slots=True)
class Replacement:
    """A new question, or the thread's last one answered again (regenerate) or rewritten (edit)."""

    kind: TurnKind
    question_id: UUID | None


@dataclass(frozen=True, slots=True)
class TurnRequest:
    """What the person sent: the question, the interface's language, whether it supersedes
    the answer still being written, the page they are on, and the question it answers again."""

    text: str
    locale: str | None
    supersede: bool
    page: Page = field(default_factory=lambda: Page(None, None))
    again: Replacement = field(default_factory=lambda: Replacement(TurnKind.NEW, None))
    # Готовые загрузки `leo_attachment` нового вопроса.
    attachments: tuple[UUID, ...] = ()


class TurnPrint(BaseModel):
    """What a turn asked: the same key with another question is a reused key."""

    thread_id: UUID
    question: str
    kind: TurnKind
    question_id: UUID | None
    attachments: list[UUID] = []


def unavailable() -> AppError:
    """Valkey or the queue did not answer: Leo cannot start a run now."""
    return AppError("agent_unavailable", HTTPStatus.SERVICE_UNAVAILABLE)


class TurnStarter:
    """Admits turns in the API."""

    def __init__(
        self,
        parts: TurnParts,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        monotonic: Callable[[], float] = time.monotonic,
        limit: RateLimit = TURN_LIMIT,
    ) -> None:
        self._parts = parts
        self._clock = clock
        self._monotonic = monotonic
        self._limit = limit

    async def start(
        self, principal: Principal, thread_id: UUID, request: TurnRequest, client_key: str
    ) -> UUID:
        """The run that answers the turn: new, or the one the key made before. The run starts
        when the request arrives, so its duration covers the checks the person waits for too."""
        received = self._clock()
        try:
            question = check_question(request.text, 0)
        except ThreadRuleError as error:
            raise AppError(error.rule.value, HTTPStatus.UNPROCESSABLE_CONTENT) from error
        asked = TurnPrint(
            thread_id=thread_id,
            question=question,
            kind=request.again.kind,
            question_id=request.again.question_id,
            attachments=list(request.attachments),
        )
        effect = EffectKey(
            TURN_KEYS, account_key(principal.user_id, client_key), fingerprint_of(asked)
        )
        parts = self._parts
        async with parts.transactions.begin(principal.scope(), read_only=True) as session:
            earlier = await parts.effects.recorded(session, effect, TurnMade)
            if earlier is not None:
                return earlier.run_id
            await parts.threads.visible_thread(session, principal.user_id, thread_id)
            consent = await parts.ports.get(CONSENT_READER).cross_border(session, principal.user_id)
            stored = await session.get(AgentSettingsRecord, principal.user_id)
            memory = await memory_switches(parts.ports, session, principal.user_id)
        if principal.home is Home.RU and not consent:
            raise AppError("consent_required", HTTPStatus.FORBIDDEN)
        # Ход оператора платит платформа (AG-D5): тарифа и его токенов у него нет, вложений тоже.
        operator = is_operator(principal.user_id)
        if operator and request.attachments:
            raise AppError("attachments_not_allowed", HTTPStatus.UNPROCESSABLE_ENTITY)
        route = (
            OPERATOR_ROUTE
            if operator
            else (await standard_tokens(self._parts.ports, principal)).value
        )
        await self._within_rate(principal)
        preferences = preferences_of(stored)
        page, again = request.page, request.again
        language = OPERATOR_LANGUAGE if operator else answer_language(preferences, request.locale)
        leo = tuple(s.value for s in Switch if preferences.switched_on(s))
        switches = () if operator else (*leo, *memory)
        terms = TurnPayload(
            home=principal.home, user_id=principal.user_id, run_id=new_id(), thread_id=thread_id,
            started_at=received, question_id=again.question_id or new_id(),
            reply_id=new_id(), language=language,
            length=preferences.response_length, cross_border_consent=consent,
            token_route=route, kind=again.kind, path=page.path,
            subject_kind=page.subject.kind if page.subject else None,
            subject_id=page.subject.subject_id if page.subject else None,
            switches_on=switches, attachments=request.attachments,
        )  # fmt: skip
        return await self._admitted(
            principal, terms, (effect, question), supersede=request.supersede
        )

    async def _admitted(
        self,
        principal: Principal,
        terms: TurnPayload,
        asked: tuple[EffectKey, str],
        *,
        supersede: bool,
    ) -> UUID:
        parts = self._parts
        try:
            admission = await parts.fleet.admit(principal.user_id, terms.run_id)
        except REDIS_FAILURES as error:
            raise unavailable() from error
        if admission is not Admission.ADMITTED:
            params = {"retry_after_seconds": BUSY_RETRY_SECONDS}
            raise AppError(admission.value, HTTPStatus.TOO_MANY_REQUESTS, params=params)
        try:
            await self._take_thread(terms.thread_id, terms.run_id, supersede=supersede)
            made = await commit_turn(parts, principal, terms, asked)
        except BaseException:
            await self._let_go(principal.user_id, terms)
            raise
        if made.run_id != terms.run_id:
            await self._let_go(principal.user_id, terms)
            return made.run_id
        for closed in made.closed:
            # Закрытому новым ходом прогону эпилог не нужен: его кадр удаляется.
            await parts.frames.forget(closed)
        try:
            await parts.run_log.append(terms.run_id, (started_event(terms),))
            await parts.tasks.send(RUN_TURN, terms)
        except (*REDIS_FAILURES, TaskQueueUnavailableError) as error:
            await abandon_turn(parts.transactions, terms, self._clock())
            await self._let_go(principal.user_id, terms)
            raise unavailable() from error
        return terms.run_id

    async def _within_rate(self, principal: Principal) -> None:
        verdict = await self._parts.limiter.check(self._limit, str(principal.user_id))
        if not verdict.allowed:
            raise RateLimitedError(verdict.retry_after)

    async def _take_thread(self, thread_id: UUID, run_id: UUID, *, supersede: bool) -> None:
        leases = self._parts.leases
        try:
            if await leases.take(thread_id, run_id):
                return
            holder = await leases.holder(thread_id)
            if supersede and holder is not None:
                await leases.ask_to_stop(holder)
                until = self._monotonic() + SUPERSEDE_WAIT.total_seconds()
                while self._monotonic() < until:
                    await asyncio.sleep(SUPERSEDE_POLL.total_seconds())
                    if await leases.take(thread_id, run_id):
                        return
        except REDIS_FAILURES as error:
            raise unavailable() from error
        raise AppError("thread_busy", HTTPStatus.CONFLICT)

    async def _let_go(self, user_id: UUID, terms: TurnPayload) -> None:
        try:
            await self._parts.leases.release(terms.thread_id, terms.run_id)
            await self._parts.fleet.release(user_id, terms.run_id)
        except REDIS_FAILURES as error:
            # Аренда и счёт истекут сами через 30 с; ответ человеку от этого не меняется.
            log.warning("Аренда хода Leo не снята", error_type=type(error).__name__)

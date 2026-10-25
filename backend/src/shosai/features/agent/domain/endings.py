"""How a run ended, kept in three places that must agree (Leo §5.1, §13.2; agent plan §3.5).

An ending says what the run's row becomes, what the answer kept in the thread is marked, and
which terminal event closes the stream: an answer is `completed` with `run.completed
{answered}`, a stopped one `completed` with `{stopped}` and the text so far, a failure
`failed` with its code in `run.failed` — the failure itself is never written into the
answer, only the text the model wrote before it. A run that proposed a write is `paused`
with its answer so far and `run.paused`; once the action is decided it closes `completed`
with the reason it had no epilogue. A run whose thread is gone is `cancelled` and keeps
nothing.
"""

from dataclasses import dataclass
from typing import Final
from uuid import UUID

from shosai.features.agent.domain.runs import CloseReason, RunFailure, RunStatus
from shosai.features.agent.domain.stream import Completion, EventData, EventKind
from shosai.features.agent.domain.threads import AnswerStatus

PAUSED_CODE: Final = "paused"
CLOSED: Final = frozenset(reason.value for reason in CloseReason)


@dataclass(frozen=True, slots=True)
class Ending:
    """The run's status and code, the kept answer's status, whether a limit cut it, and the
    action a paused run waits for."""

    status: RunStatus
    code: str
    answer: AnswerStatus | None
    truncated: bool = False
    action_id: UUID | None = None

    def terminal(self, reply_id: UUID | None) -> tuple[EventKind, EventData]:
        """The event that closes the run's stream — for now, when it pauses; the answer's id,
        when one was kept."""
        if self.status is RunStatus.FAILED:
            return EventKind.RUN_FAILED, {"code": self.code}
        if self.status is RunStatus.PAUSED:
            return EventKind.RUN_PAUSED, {"action_id": str(self.action_id)}
        # Отменённый удалением треда прогон закрывается для клиента как остановленный.
        answered_now = self.code == Completion.ANSWERED or self.code in CLOSED
        outcome = Completion.ANSWERED if answered_now else Completion.STOPPED
        return EventKind.RUN_COMPLETED, {
            "message_id": None if reply_id is None else str(reply_id),
            "outcome": outcome.value,
            "truncated": self.truncated,
        }

    def keeps(self, text: str) -> bool:
        """Whether the answer is written into the thread: a finished one always, a stopped or
        failed one when the model wrote something before."""
        if self.answer is None:
            return False
        return self.answer is AnswerStatus.DONE or bool(text)


def answered(*, truncated: bool) -> Ending:
    """The model finished its answer; `truncated` when a token limit cut it."""
    return Ending(RunStatus.COMPLETED, Completion.ANSWERED.value, AnswerStatus.DONE, truncated)


def stopped() -> Ending:
    """The person stopped the answer, or a new turn superseded it."""
    return Ending(RunStatus.COMPLETED, Completion.STOPPED.value, AnswerStatus.STOPPED)


def failed(failure: RunFailure) -> Ending:
    """The run failed with a code the client words."""
    return Ending(RunStatus.FAILED, failure.value, AnswerStatus.FAILED)


def paused(action_id: UUID) -> Ending:
    """The run proposed a write and waits for the person; the answer so far is kept."""
    return Ending(RunStatus.PAUSED, PAUSED_CODE, AnswerStatus.DONE, action_id=action_id)


def closed(reason: CloseReason) -> Ending:
    """A paused run closed after its action was decided, without an epilogue."""
    return Ending(RunStatus.COMPLETED, reason.value, AnswerStatus.DONE)


def cancelled() -> Ending:
    """The thread was deleted while the run went on: nothing is kept."""
    return Ending(RunStatus.CANCELLED, "thread_deleted", None)


def recorded(status: RunStatus, code: str | None) -> Ending | None:
    """The ending a run's row records; None while the run is not over."""
    if status is RunStatus.FAILED:
        known = {failure.value for failure in RunFailure}
        return failed(RunFailure(code) if code in known else RunFailure.FAILED)
    if status is RunStatus.COMPLETED:
        if code in CLOSED:
            return closed(CloseReason(code))
        return answered(truncated=False) if code == Completion.ANSWERED else stopped()
    if status is RunStatus.CANCELLED:
        return cancelled()
    return None

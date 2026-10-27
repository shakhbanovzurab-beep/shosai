"""What a decision returns and records: its source, its reason and its subject (ADR 0069).

The source says who settled the outcome — the consumer's rule, a fallback taken in its
place, Jev, or Jev answering after the caller had moved on. The reason is a code from a
closed set, so the *why* of every outcome is deterministic even when Jev decided it
(Leo §6.1: Jev gives no rationale). The subject names what was decided about by id: a run,
an action, or a piece of text within a run.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class DecisionSource(StrEnum):
    """Who settled an outcome."""

    RULE = "rule"
    FALLBACK = "fallback"
    JEV = "jev"
    # Ответ Jev после срока: вызывающий уже получил правило, запись — для калибровки.
    LATE = "late"


class DecisionReason(StrEnum):
    """Why an outcome is what it is."""

    # Политике нечего менять: всё помещается, правило уже осторожно; только счётчик.
    NOTHING_TO_DECIDE = "nothing_to_decide"
    POLICY_OFF = "policy_off"
    # Эндпоинт Jev не в списке нулевого хранения OpenRouter или список устарел (ADR 0069).
    NOT_ZDR = "not_zdr"
    NO_CONSENT = "no_consent"
    BUSY = "busy"
    DEADLINE = "deadline"
    PROVIDER_ERROR = "provider_error"
    CONTRACT = "contract"
    BUDGET = "budget"
    JUDGED = "judged"


class SubjectKind(StrEnum):
    """What a decision is about."""

    RUN = "run"
    ACTION = "action"
    # Кусок текста в прогоне: id прогона и номер куска.
    TEXT = "text"


@dataclass(frozen=True, slots=True)
class Subject:
    """The decided thing by id; `part` numbers pieces within it."""

    kind: SubjectKind
    id: UUID
    part: int = 0

    def __post_init__(self) -> None:
        if self.part < 0:
            message = "номер куска не бывает отрицательным"
            raise ValueError(message)

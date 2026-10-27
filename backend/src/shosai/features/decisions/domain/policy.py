"""A policy: one decision point's questions, state, verdicts and outcome (Leo §6.2, ADR 0026).

A policy is code, versioned and reviewed like code. It declares its point and version, the
questions it asks Jev (English, registered in the model-facing test), the signal each
answer gives and the cut it is read through, the state Jev reads and the facts recorded,
the deadline, and how verdicts become an outcome. Its thresholds are not in the code: they
are a revision of platform data fitted by calibration (§6.4), so a refit is a new revision
and a new question text is a new version.

Monotonic safety is the policy's to keep: the consumer's rule decides first and the final
outcome is `careful(rule, judged)` — Jev may only make the outcome more careful, never less
(ADR 0026 point 3). A policy also says when it has nothing to decide (`settled`), so no call
is made where the rule's answer cannot change.
"""

import hashlib
import json
from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import timedelta
from typing import Final

from shosai.core.ai.decisions import ChoiceQuestion, Question, ScoreQuestion
from shosai.features.decisions.domain.calibration import Aims
from shosai.features.decisions.domain.state import DEFAULT_BUDGET, Fact
from shosai.features.decisions.domain.verdicts import Signal, Verdict

POINT_NAME_MAX: Final = 40


class Policy[F, V](ABC):
    """One version of the policy of a decision point over facts `F` and outcomes `V`."""

    point: str
    version: int
    deadline: timedelta
    # Пороги, которые задаёт ревизия калибровки, по именам сигналов, и их цели подгонки.
    cuts: tuple[str, ...]
    aims: Aims
    budget: int = DEFAULT_BUDGET
    # Читает согласие человека (voice.approval, ограниченное исключение владельца от
    # 2026-10-27): исход может быть мягче правила — только из ответа активной версии в срок.
    reads_consent: bool = False

    @property
    def key(self) -> str:
        """`point@version`, as records and reports name the policy."""
        return f"{self.point}@{self.version}"

    @abstractmethod
    def settled(self, facts: F, rule: V) -> bool:
        """Whether the rule's outcome cannot change, so nothing is asked."""

    @abstractmethod
    def questions(self, facts: F) -> Mapping[str, Question]:
        """The questions asked about these facts, by name."""

    @abstractmethod
    def signals(self, facts: F) -> Mapping[str, Signal]:
        """The signal of each question's answer, by the question's name."""

    @abstractmethod
    def state(self, facts: F) -> dict[str, object]:
        """The state Jev reads, within `budget`."""

    @abstractmethod
    def facts(self, facts: F) -> Mapping[str, Fact]:
        """What a record keeps of the facts: numbers, booleans and codes of closed sets."""

    @abstractmethod
    def outcome(self, facts: F, verdicts: Mapping[str, Verdict], chances: Mapping[str, float]) -> V:
        """The judged outcome; an unsure verdict takes the careful side."""

    @abstractmethod
    def careful(self, rule: V, judged: V) -> V:
        """The final outcome: never less careful than the rule."""

    @abstractmethod
    def less_careful(self, value: V, rule: V) -> bool:
        """Whether an outcome is less careful than the rule's — an invariant breach."""

    @abstractmethod
    def code(self, value: V) -> str:
        """The outcome as a record's code."""

    @abstractmethod
    def parse_facts(self, raw: Mapping[str, object]) -> F:
        """The facts of a dataset's case; `ValueError` when they are not this policy's."""

    @abstractmethod
    def careful_case(self, expected: V) -> bool:
        """Whether a case's expected outcome is the careful one its gate counts."""

    def agrees(self, judged: V, expected: V) -> bool:
        """Whether a judged outcome is the expected one."""
        return judged == expected

    def band(self, outcome: str) -> str:
        """The band a recorded outcome's code falls in, for the daily reliability counts."""
        return outcome

    def confirms(self, outcome: str, observation: Mapping[str, object] | None) -> bool:
        """Whether what followed a recorded decision is the careful outcome's case; False when
        nothing followed or the point observes nothing."""
        del outcome, observation
        return False

    @abstractmethod
    def wording(self) -> Mapping[str, object]:
        """Every fixed text of the questions, as the model-facing test and the digest read it."""

    def digest(self) -> str:
        """A hash of the questions' wording: an image whose wording differs from the promoted
        version's never uses that version's thresholds."""
        canonical = json.dumps(self.wording(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def question_text(question: Question) -> dict[str, object]:
    """A question as plain data: what Jev reads of it."""
    if isinstance(question, ChoiceQuestion):
        return {"instructions": question.instructions, "criteria": dict(question.criteria)}
    if isinstance(question, ScoreQuestion):
        return {"instructions": question.instructions, "criteria": list(question.criteria)}
    sides = {"true": question.when_true, "false": question.when_false}
    return {"instructions": question.instructions, "criteria": sides}


def check_point(name: str) -> str:
    """A point's name: lowercase words joined by dots, as `turn.route`."""
    words = name.split(".")
    if len(name) > POINT_NAME_MAX or len(words) != 2 or not all(w.isidentifier() for w in words):
        message = f"имя точки решения — два слова через точку: {name!r}"
        raise ValueError(message)
    if name != name.lower():
        message = f"имя точки решения — строчными: {name!r}"
        raise ValueError(message)
    return name

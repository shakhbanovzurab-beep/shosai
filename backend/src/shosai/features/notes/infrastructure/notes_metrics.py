"""What the notes' model answered (§16.6): read, read when asked again, or lost.

`shosai_notes_model_answers_total{call, outcome}` counts the answers of each call — a
window of the findings, their merge, the summary — by outcome: `read` the first time,
`read_again` after one more question, `lost` when the second answer was no better. A lost
window leaves its findings out of the notes; a lost summary leaves the section empty.
"""

from enum import StrEnum
from typing import Final

from prometheus_client import CollectorRegistry, Counter

MODEL_ANSWERS: Final = "shosai_notes_model_answers_total"


class NotesCall(StrEnum):
    """Which call of the notes the model answered."""

    WINDOW = "window"
    MERGE = "merge"
    SUMMARY = "summary"


class AnswerOutcome(StrEnum):
    """What came of a call's answer."""

    READ = "read"
    READ_AGAIN = "read_again"
    LOST = "lost"


class NotesMetrics:
    """The counter of the model's answers, in the process's registry."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._answers = Counter(
            MODEL_ANSWERS.removesuffix("_total"),
            "Ответы модели заметок по вызову и исходу",
            ("call", "outcome"),
            registry=registry,
        )

    def answered(self, call: NotesCall, outcome: AnswerOutcome) -> None:
        """Count one answer."""
        self._answers.labels(call=call.value, outcome=outcome.value).inc()

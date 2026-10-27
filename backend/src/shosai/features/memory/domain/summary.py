"""The overview the person reads in Settings > Memory, and its checks (SM-6, ADR 0071).

The summary is derived from the current facts and kept only when its shape holds: one to
five titled sections of plain prose — no Markdown, no lists, no code — and at most three
suggested questions. The draft showed a summary that started mid-sentence, carried reasoning
or bold text; such an answer is refused and the last good summary stays.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

SECTIONS_MAX: Final = 5
TITLE_MAX: Final = 80
BODY_MAX: Final = 1_200
SUGGESTIONS_MAX: Final = 3
SUGGESTION_MAX: Final = 160
# Разметка, которой в прозе сводки быть не должно: заголовки, списки, жирный, код, ссылки.
_MARKUP: Final = re.compile(r"(?m)^\s*(?:#{1,6}\s|[-*+]\s|\d+[.)]\s|>)|\*\*|__|`|\[[^\]]*\]\(")


class SummaryProblem(StrEnum):
    """Why a written summary is refused."""

    NO_SECTIONS = "no_sections"
    TOO_MANY = "too_many"
    EMPTY = "empty"
    TOO_LONG = "too_long"
    MARKUP = "markup"
    REPEATED = "repeated"


class SummaryRefusedError(ValueError):
    """A written summary breaks its shape; `problem` says how."""

    def __init__(self, problem: SummaryProblem) -> None:
        super().__init__(problem.value)
        self.problem = problem


@dataclass(frozen=True, slots=True)
class Section:
    """A titled part of the summary."""

    title: str
    body: str


@dataclass(frozen=True, slots=True)
class Summary:
    """A summary whose shape holds."""

    sections: tuple[Section, ...]
    suggestions: tuple[str, ...]


EMPTY_SUMMARY: Final = Summary((), ())


def _text(value: str, limit: int) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise SummaryRefusedError(SummaryProblem.EMPTY)
    if len(cleaned) > limit:
        raise SummaryRefusedError(SummaryProblem.TOO_LONG)
    if _MARKUP.search(cleaned):
        raise SummaryRefusedError(SummaryProblem.MARKUP)
    return cleaned


def checked(sections: Sequence[tuple[str, str]], suggestions: Sequence[str]) -> Summary:
    """The summary when its shape holds; `SummaryRefusedError` otherwise."""
    if not sections:
        raise SummaryRefusedError(SummaryProblem.NO_SECTIONS)
    if len(sections) > SECTIONS_MAX or len(suggestions) > SUGGESTIONS_MAX:
        raise SummaryRefusedError(SummaryProblem.TOO_MANY)
    kept = tuple(
        Section(_text(title, TITLE_MAX), _text(body, BODY_MAX)) for title, body in sections
    )
    asked = tuple(_text(question, SUGGESTION_MAX) for question in suggestions)
    titles = [section.title.casefold() for section in kept]
    if len(set(titles)) != len(titles) or len({q.casefold() for q in asked}) != len(asked):
        raise SummaryRefusedError(SummaryProblem.REPEATED)
    return Summary(kept, asked)

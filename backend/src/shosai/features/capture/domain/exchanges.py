"""What both sides said in one exchange of a voice conversation (ADR 0070, LV-D5).

Gemini sends each side's words in pieces as it hears them, spaces included, and marks the
last piece of a phrase. The person's pieces are their phrase until it is finished; what
they say while Leo answers after that belongs to the next phrase — the person may speak
over Leo — and opens the next exchange. An exchange begins with its first word or tool call
and ends when Leo, having said something, finishes its turn or is interrupted.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class Phrase:
    """The person's pieces of one phrase."""

    pieces: list[str] = field(default_factory=list)
    finished: bool = False

    @property
    def text(self) -> str:
        """The phrase so far."""
        return "".join(self.pieces).strip()


@dataclass(slots=True)
class Exchange:
    """One exchange so far."""

    started_at: datetime | None = None
    heard: Phrase = field(default_factory=Phrase)
    said: list[str] = field(default_factory=list)
    # Слова человека поверх ответа Leo, когда его фраза уже закончена: начало следующей.
    overheard: Phrase = field(default_factory=Phrase)
    calls: int = 0

    @property
    def question(self) -> str:
        """The person's phrase."""
        return self.heard.text

    @property
    def answer(self) -> str:
        """Leo's words."""
        return "".join(self.said).strip()

    @property
    def answered(self) -> bool:
        """Leo said something or called a tool: a turn's end closes the exchange."""
        return bool(self.answer) or self.calls > 0

    @property
    def empty(self) -> bool:
        """Nothing was said and no tool was called."""
        return not self.question and not self.answered

    def hear(self, piece: str, at: datetime, *, final: bool) -> Phrase:
        """A piece of the person's speech; the phrase it belongs to."""
        self._begin(at)
        phrase = self.overheard if self.heard.finished and self.said else self.heard
        phrase.pieces.append(piece)
        phrase.finished = phrase.finished or final
        return phrase

    def say(self, piece: str, at: datetime) -> str:
        """A piece of Leo's speech; its words so far."""
        self._begin(at)
        self.said.append(piece)
        return self.answer

    def call(self, at: datetime) -> None:
        """Leo called a tool."""
        self._begin(at)
        self.calls += 1

    def following(self, at: datetime) -> Exchange:
        """The next exchange, opened by what the person said over Leo, if anything."""
        if not self.overheard.text:
            return Exchange()
        return Exchange(started_at=at, heard=self.overheard)

    def _begin(self, at: datetime) -> None:
        if self.started_at is None:
            self.started_at = at

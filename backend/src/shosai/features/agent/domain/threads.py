"""A conversation with Leo and the space it belongs to (agent plan §3.4, ADR 0068 AG-D2, AG-D3).

A thread belongs to one person and one scope — their Personal space, a workspace, or a hub —
and the scope ranks its own space first when Leo reads and is where Leo writes by default
(ADR 0039). A thread is the person's own: never shared, kept until they delete it. A
workspace's threads disappear for the person the moment their membership ends and are erased
7 days later unless it is active again (AG-D3). A question is 1 to 4 000 characters with up to
five attachments; "Regenerate" and "Edit" act on the thread's last question only.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final
from uuid import UUID

TITLE_MAX: Final = 120
QUESTION_MAX: Final = 4_000
ATTACHMENTS_MAX: Final = 5
SURFACE_PATH_MAX: Final = 200
ERASURE_DELAY: Final = timedelta(days=7)
# Заголовок из вопроса режется по последнему пробелу, если он не дальше этого от края.
TITLE_WORD_SLACK: Final = 30
ELLIPSIS: Final = "…"


class ScopeKind(StrEnum):
    """Which space a thread belongs to."""

    PERSONAL = "personal"
    WORKSPACE = "workspace"
    HUB = "hub"


class ThreadRule(StrEnum):
    """A rule of threads and turns; the value is the API's error code."""

    TITLE_INVALID = "title_invalid"
    QUESTION_INVALID = "question_invalid"
    TOO_MANY_ATTACHMENTS = "too_many_attachments"
    NOT_LAST_QUESTION = "not_last_question"
    SCOPE_INVALID = "scope_invalid"
    # Треды хаба приходят с хабами (шаг 20).
    SCOPE_UNAVAILABLE = "scope_unavailable"


class ThreadRuleError(ValueError):
    """A thread or a turn breaks one of the rules; `rule` is the API's code."""

    def __init__(self, rule: ThreadRule) -> None:
        super().__init__(rule.value)
        self.rule = rule


@dataclass(frozen=True, slots=True)
class ThreadScope:
    """The space of a thread: Personal, one workspace, or one hub."""

    kind: ScopeKind
    org_id: UUID | None = None
    hub_id: UUID | None = None

    def __post_init__(self) -> None:
        expected = (self.kind is ScopeKind.WORKSPACE, self.kind is ScopeKind.HUB)
        if (self.org_id is not None, self.hub_id is not None) != expected:
            raise ThreadRuleError(ThreadRule.SCOPE_INVALID)

    @classmethod
    def personal(cls) -> ThreadScope:
        """The person's own space."""
        return cls(ScopeKind.PERSONAL)


class MessageRole(StrEnum):
    """Who wrote a row of a thread; `tool` rows are the model's context, never listed."""

    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SERVER = "server"


class HistoryRole(StrEnum):
    """Who wrote a row the history lists: the person, Leo, or the server's note."""

    USER = "user"
    ASSISTANT = "assistant"
    SERVER = "server"


class AnswerStatus(StrEnum):
    """How an answer ended; a failure is never written into the text."""

    DONE = "done"
    STOPPED = "stopped"
    FAILED = "failed"


class TurnKind(StrEnum):
    """What a turn does to the thread."""

    NEW = "new"
    # Тот же последний вопрос, ответ заново.
    REGENERATE = "regenerate"
    # Последний вопрос переписан, ответ заново.
    EDIT = "edit"


def check_available(kind: ScopeKind) -> None:
    """A hub's threads come with hubs (agent plan step 20); until then the scope is refused."""
    if kind is ScopeKind.HUB:
        raise ThreadRuleError(ThreadRule.SCOPE_UNAVAILABLE)


def clean_title(raw: str) -> str:
    """A title the person typed: trimmed, runs of whitespace as one space, 1 to 120 characters."""
    title = " ".join(raw.split())
    if not 0 < len(title) <= TITLE_MAX:
        raise ThreadRuleError(ThreadRule.TITLE_INVALID)
    return title


def title_from_question(question: str) -> str:
    """A thread's first title: the question's first line, cut at a word when it can be."""
    first = " ".join(next((line for line in question.splitlines() if line.strip()), "").split())
    if len(first) <= TITLE_MAX:
        return first or ELLIPSIS
    head = first[: TITLE_MAX - len(ELLIPSIS)]
    space = head.rfind(" ")
    if space >= len(head) - TITLE_WORD_SLACK:
        head = head[:space]
    return head.rstrip() + ELLIPSIS


def check_question(text: str, attachments: int) -> str:
    """A question's text, trimmed: 1 to 4 000 characters, or empty with an attachment; 5 files."""
    if attachments > ATTACHMENTS_MAX:
        raise ThreadRuleError(ThreadRule.TOO_MANY_ATTACHMENTS)
    question = text.strip()
    if len(question) > QUESTION_MAX or (not question and attachments == 0):
        raise ThreadRuleError(ThreadRule.QUESTION_INVALID)
    return question


def check_replacement(kind: TurnKind, named: UUID | None, last_question: UUID | None) -> None:
    """A regenerate or an edit names the thread's last question; a new turn names none."""
    if kind is TurnKind.NEW:
        if named is not None:
            raise ThreadRuleError(ThreadRule.NOT_LAST_QUESTION)
        return
    if named is None or named != last_question:
        raise ThreadRuleError(ThreadRule.NOT_LAST_QUESTION)


class Erasure(StrEnum):
    """What the daily purge does with a departed workspace's thread (AG-D3)."""

    WAIT = "wait"
    ERASE = "erase"
    # Членство снова активно: метка снимается, тред возвращается.
    RESTORED = "restored"


def erase_after(departed_at: datetime) -> datetime:
    """When a thread of a workspace the person left is erased unless they are back."""
    return departed_at + ERASURE_DELAY


def erasure(due: datetime, now: datetime, *, member_again: bool) -> Erasure:
    """The purge's verdict: a restored membership keeps the thread, a lapsed one erases it."""
    if member_again:
        return Erasure.RESTORED
    return Erasure.ERASE if now >= due else Erasure.WAIT

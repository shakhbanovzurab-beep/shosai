"""What a tool's result stands on and what it hands over (ADR 0068 AG-D1, agent plan AG-R1).

A read tool names the sources of its result as `SourceRef`s: the kind and id of each, its
title, the workspace it belongs to (none for the person's own Personal space), a place
inside it and the quote the result rests on. The agent numbers them for the model, which
cites them by number, so a source in an answer is always one a tool returned — never one the
model wrote. An `ArtifactRef` is a result read apart from the answer, by reference: a chat's
digest that chats keeps, a chart or an image later; the stream carries the reference only.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final
from uuid import UUID

SOURCE_ID_MAX: Final = 2_048
TITLE_MAX: Final = 200
LOCATOR_MAX: Final = 80
QUOTE_MAX: Final = 1_000
REF_MAX: Final = 120
ALT_MAX: Final = 300
FIELD_NAME: Final = re.compile(r"[a-z][a-z0-9_]{0,39}")


class SourceKind(StrEnum):
    """What a source is; the cabinet picks its icon by the kind."""

    MEETING = "meeting"
    FILE = "file"
    TASK = "task"
    NOTE = "note"
    MAIL = "mail"
    WEB = "web"


@dataclass(frozen=True, slots=True)
class SourceRef:
    """One thing a result rests on, in the space it belongs to."""

    kind: SourceKind
    # Ид в своём срезе (UUID встречи, файла, задачи) или адрес страницы веба.
    id: str
    title: str
    # Пространство источника: workspace или None — личное пространство человека.
    org_id: UUID | None = None
    # Место внутри источника: время в записи, страница; None — без места.
    locator: str | None = None
    quote: str = ""

    def __post_init__(self) -> None:
        problems = []
        if not 0 < len(self.id) <= SOURCE_ID_MAX:
            problems.append(f"ид источника обязателен и не длиннее {SOURCE_ID_MAX} символов")
        if not self.title.strip() or len(self.title) > TITLE_MAX:
            problems.append(f"название источника — от 1 до {TITLE_MAX} символов")
        if self.locator is not None and not 0 < len(self.locator) <= LOCATOR_MAX:
            problems.append(f"место в источнике — от 1 до {LOCATOR_MAX} символов")
        if len(self.quote) > QUOTE_MAX:
            problems.append(f"отрывок источника не длиннее {QUOTE_MAX} символов")
        if problems:
            raise ValueError("; ".join(problems))

    @property
    def identity(self) -> tuple[SourceKind, str, str | None]:
        """What makes two references the same source: the same place in the same thing."""
        return self.kind, self.id, self.locator


class ArtifactKind(StrEnum):
    """What an artifact is; each kind names the fields the cabinet needs to read it."""

    # Дайджест командного чата: хранит срез chats 30 дней (AG-R1).
    CHAT_DIGEST = "chat_digest"


ARTIFACT_FIELDS: Final[Mapping[ArtifactKind, frozenset[str]]] = {
    ArtifactKind.CHAT_DIGEST: frozenset({"workspace_id", "chat_id"}),
}


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """A result read apart from the answer, by its reference; never its content."""

    kind: ArtifactKind
    ref: str
    # Подпись для тех, кто карточку не видит; слова среза, на языке человека.
    alt: str
    fields: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        problems = []
        if not 0 < len(self.ref) <= REF_MAX:
            problems.append(f"ссылка артефакта — от 1 до {REF_MAX} символов")
        if not self.alt.strip() or len(self.alt) > ALT_MAX:
            problems.append(f"подпись артефакта — от 1 до {ALT_MAX} символов")
        if set(self.fields) != ARTIFACT_FIELDS[self.kind]:
            problems.append(f"артефакт {self.kind}: поля {sorted(ARTIFACT_FIELDS[self.kind])}")
        if any(not FIELD_NAME.fullmatch(name) or not value for name, value in self.fields.items()):
            problems.append("поля артефакта — имена в snake_case с непустыми значениями")
        if problems:
            raise ValueError("; ".join(problems))

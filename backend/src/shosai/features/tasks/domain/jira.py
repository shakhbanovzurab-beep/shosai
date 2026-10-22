"""How a Jira issue and a task map onto each other (TK-D8; draft lessons of `features/jira`).

Status bridges by Jira's status category, never by a status's name: `new` is to do,
`indeterminate` in progress, `done` done, and `undefined` — or anything else — never done.
Priority bridges by the ids of Jira's default scheme (1 Highest … 5 Lowest), the same on
every site and in every language, never by a priority's name; a priority outside that
scheme is unmapped: it neither changes the task nor is ever written back. A due date is a
calendar day both ways. A description in Atlassian Document Format reads as plain text,
and a task's text goes out as plain paragraphs.
"""

from collections.abc import Mapping
from datetime import date
from enum import Enum, StrEnum
from typing import Final

from pydantic import JsonValue

from shosai.features.tasks.domain.tasks import TITLE_MAX, Priority, TaskStatus


class StatusCategory(StrEnum):
    """Jira's status categories, by their keys."""

    NEW = "new"
    INDETERMINATE = "indeterminate"
    DONE = "done"
    UNDEFINED = "undefined"


STATUS_OF_CATEGORY: Final = {
    StatusCategory.NEW.value: TaskStatus.TODO,
    StatusCategory.INDETERMINATE.value: TaskStatus.IN_PROGRESS,
    StatusCategory.DONE.value: TaskStatus.DONE,
}
CATEGORY_OF_STATUS: Final = {
    TaskStatus.TODO: StatusCategory.NEW,
    TaskStatus.IN_PROGRESS: StatusCategory.INDETERMINATE,
    TaskStatus.DONE: StatusCategory.DONE,
}


def status_of(category_key: str) -> TaskStatus:
    """The task status of a Jira status category; an unknown or undefined one is to do."""
    return STATUS_OF_CATEGORY.get(category_key, TaskStatus.TODO)


def category_of(status: TaskStatus) -> StatusCategory:
    """The Jira status category a task of this status needs: its column's statuses have it."""
    return CATEGORY_OF_STATUS[status]


class Unmapped(Enum):
    """A Jira priority outside its default scheme."""

    UNMAPPED = "unmapped"


UNMAPPED: Final = Unmapped.UNMAPPED
# Идентификаторы схемы приоритетов Jira по умолчанию: одинаковы на любом сайте и языке.
PRIORITY_OF_ID: Final = {
    "1": Priority.HIGH,
    "2": Priority.HIGH,
    "3": Priority.MEDIUM,
    "4": Priority.LOW,
    "5": Priority.LOW,
}
ID_OF_PRIORITY: Final = {Priority.HIGH: "2", Priority.MEDIUM: "3", Priority.LOW: "4"}


def priority_of(priority_id: str | None) -> Priority | Unmapped | None:
    """The task priority of a Jira priority id; none for no priority, `UNMAPPED` otherwise."""
    if priority_id is None:
        return None
    return PRIORITY_OF_ID.get(priority_id, UNMAPPED)


def priority_after_pull(current: Priority | None, priority_id: str | None) -> Priority | None:
    """The task's priority after reading the issue: an unmapped one leaves it as it is."""
    mapped = priority_of(priority_id)
    return current if isinstance(mapped, Unmapped) else mapped


def jira_priority_id(priority: Priority | None) -> str | None:
    """The Jira priority id to write, or none: an empty priority is never written."""
    return None if priority is None else ID_OF_PRIORITY[priority]


def due_of(raw: str | None) -> date | None:
    """Jira's due date as a calendar day; anything unreadable is none."""
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def title_of(summary: str) -> str:
    """The task's title from an issue's summary, cut to 200 characters."""
    return " ".join(summary.split())[:TITLE_MAX].rstrip()


# Блоки ADF, чей текст — их встроенные узлы; списки помечаются, остальное читается насквозь.
INLINE_BLOCKS: Final = frozenset({"paragraph", "heading", "codeBlock"})
INLINE_NODES: Final = frozenset({"text", "hardBreak", "mention", "emoji", "status", "date"})
# Глубже документ задачи не вложен; вложенность сверх этого — чужой мусор, её текст пропускается.
DEPTH_MAX: Final = 32


def text_of_document(document: Mapping[str, JsonValue] | None) -> str:
    """The plain text of an ADF document: blocks on their own lines, list items marked."""
    if document is None:
        return ""
    return "\n".join(line.rstrip() for line in _lines(document, 0)).strip()


def _children(node: Mapping[str, JsonValue]) -> list[Mapping[str, JsonValue]]:
    content = node.get("content")
    if not isinstance(content, list):
        return []
    return [child for child in content if isinstance(child, Mapping)]


def _lines(node: Mapping[str, JsonValue], depth: int) -> list[str]:
    if depth > DEPTH_MAX:
        return []
    kind = _kind(node)
    children = _children(node)
    if kind in INLINE_BLOCKS or kind in INLINE_NODES:
        inline = [node] if kind in INLINE_NODES else children
        return "".join(_inline(child) for child in inline).split("\n")
    if kind in {"bulletList", "orderedList"}:
        lines: list[str] = []
        for index, item in enumerate(children):
            marker = "- " if kind == "bulletList" else f"{index + 1}. "
            item_lines = _lines(item, depth + 1) or [""]
            lines.append(marker + item_lines[0])
            lines.extend("  " + line for line in item_lines[1:])
        return lines
    return [line for child in children for line in _lines(child, depth + 1)]


def _kind(node: Mapping[str, JsonValue]) -> str:
    kind = node.get("type")
    return kind if isinstance(kind, str) else ""


def _inline(node: Mapping[str, JsonValue]) -> str:
    kind = _kind(node)
    if kind == "text":
        text = node.get("text")
        return text if isinstance(text, str) else ""
    if kind == "hardBreak":
        return "\n"
    attrs = node.get("attrs")
    if kind in INLINE_NODES and isinstance(attrs, Mapping):
        for key in ("text", "shortName", "timestamp"):
            value = attrs.get(key)
            if isinstance(value, str):
                return value
    return ""


def document_of_text(text: str) -> dict[str, JsonValue]:
    """An ADF document holding the text as plain paragraphs, one per non-empty line."""
    paragraphs: list[JsonValue] = [
        {"type": "paragraph", "content": [{"type": "text", "text": line}]}
        for line in (raw.rstrip() for raw in text.splitlines())
        if line
    ]
    return {"type": "doc", "version": 1, "content": paragraphs}

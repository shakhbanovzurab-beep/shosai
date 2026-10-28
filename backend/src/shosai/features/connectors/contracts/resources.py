"""One browse for every scope picker: folders, spaces, repositories, channels, projects, sites.

Knowledge's sources, chats' channels and Leo's destinations pick where something lives
through the same shape. A provider's step brings the browser of its app; a kind the app does
not have is refused.
"""

from dataclasses import dataclass
from typing import Final

MAX_PAGE: Final = 100


@dataclass(frozen=True, slots=True)
class ResourceQuery:
    """What to list: a kind, under a parent or at the top, filtered by a text, a page at a time."""

    kind: str
    parent: str | None = None
    text: str | None = None
    cursor: str | None = None
    limit: int = 50

    def __post_init__(self) -> None:
        if not 1 <= self.limit <= MAX_PAGE:
            message = f"страница ресурсов — от 1 до {MAX_PAGE}"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class Resource:
    """One place at the provider; `url` opens it there."""

    id: str
    name: str
    kind: str
    parent_id: str | None
    has_children: bool
    url: str | None


@dataclass(frozen=True, slots=True)
class ResourcePage:
    """A page of resources and the cursor of the next one."""

    items: tuple[Resource, ...]
    next_cursor: str | None

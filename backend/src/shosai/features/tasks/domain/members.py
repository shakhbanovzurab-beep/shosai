"""Whom a name from a meeting means among a workspace's members (TK-D3).

The name an action item gives is matched to the one member whose name equals it, compared
without case, width or spacing differences — the same in every language, no word lists.
No member or several members of that name: the task stays unassigned with the name kept.
"""

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class MemberName:
    """A member of a workspace and the name the workspace shows for them."""

    user_id: UUID
    name: str


def name_key(name: str) -> str:
    """A name reduced for comparison: NFKC, case folded, spaces collapsed."""
    return " ".join(unicodedata.normalize("NFKC", name).casefold().split())


def match_member(name: str, members: Sequence[MemberName]) -> UUID | None:
    """The one member whose name equals `name`, or none when no one or several do."""
    key = name_key(name)
    if not key:
        return None
    matched = {member.user_id for member in members if name_key(member.name) == key}
    return next(iter(matched)) if len(matched) == 1 else None

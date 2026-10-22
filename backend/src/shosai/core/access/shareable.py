"""Shareable resources: the tables whose rows one access policy guards (§7, ADR 0053).

A slice declares each table it lets people share — meetings, notes, folders, files,
knowledge items — on its `FeatureModule.shareable`, naming the columns the access policy
reads: the row's id, its personal owner, its workspace and its access level. The policy
(`workspaces`) builds its predicate from these columns, and the isolation gate refuses a
declared resource whose read paths have no isolation test (§14 rule 12). The declaration
lives in core because core's `FeatureModule` lists it and core cannot import a slice.

A workspace's row may also open to whoever may read its *parent* row now — a resource of
another kind, named by kind and reached through a column of this table — and to the active
member a *named reader* column names (ADR 0059): a meeting's task opens to the meeting's
readers and to its assignee. Both rules widen reading only, never managing access.
"""

import re
from dataclasses import dataclass
from typing import Final

from sqlalchemy import Table

RESOURCE_KIND: Final = re.compile(r"[a-z][a-z0-9_]{0,31}")


class ShareableResourceError(ValueError):
    """A declaration names a kind or a column the rules or the table do not allow."""


@dataclass(frozen=True, slots=True)
class ShareableResource:
    """One table whose rows are shared through the access policy, and its columns.

    Personal rows have `org` and `access` empty; a workspace's rows have both (§7). The
    kind is the stable name grants, audit events and Leo's sources use for the resource.
    """

    kind: str
    table: Table
    id: str = "id"
    owner: str = "user_id"
    org: str = "org_id"
    access: str = "access"
    # Родитель строки: вид его ресурса и колонка этой таблицы с id родителя.
    parent: tuple[str, str] | None = None
    # Колонка с пользователем-участником, которому строка пространства видна всегда.
    reader: str | None = None

    def __post_init__(self) -> None:
        if not RESOURCE_KIND.fullmatch(self.kind):
            message = f"ресурс {self.kind!r}: вид — snake_case до 32 символов"
            raise ShareableResourceError(message)
        if self.parent is not None and (
            not RESOURCE_KIND.fullmatch(self.parent[0]) or self.parent[0] == self.kind
        ):
            message = f"ресурс {self.kind}: родитель — другой вид в snake_case"
            raise ShareableResourceError(message)
        named = [*self.column_names(), *self.rule_columns()]
        missing = [name for name in named if name not in self.table.c]
        if missing:
            message = f"ресурс {self.kind}: в таблице {self.table.name} нет колонок {missing}"
            raise ShareableResourceError(message)

    def column_names(self) -> tuple[str, str, str, str]:
        """The names of the id, owner, workspace and access columns, in that order."""
        return (self.id, self.owner, self.org, self.access)

    def rule_columns(self) -> tuple[str, ...]:
        """The columns of the parent and named-reader rules, those the resource declares."""
        parent = (self.parent[1],) if self.parent is not None else ()
        reader = (self.reader,) if self.reader is not None else ()
        return (*parent, *reader)

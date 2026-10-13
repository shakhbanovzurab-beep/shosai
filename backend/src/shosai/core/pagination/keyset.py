"""Keyset pagination in SQL: the rows after a position, in the order of a sort key (§10).

The next page is a range scan from the last position, `(k1, k2) > (:k1, :k2)`, so every page
costs the same at any depth and rows inserted between pages neither repeat nor shift the
ones already shown, unlike an offset. The sort key ends with a unique column and has one
direction for all its columns (a row comparison cannot mix them); its columns are NOT NULL
and backed by an index in that order.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import ColumnElement, Select, tuple_


@dataclass(frozen=True, slots=True)
class Keyset:
    """A collection's sort key: its columns, a unique one last, and its direction."""

    columns: tuple[ColumnElement[Any], ...]
    descending: bool = False

    def __post_init__(self) -> None:
        if not self.columns:
            message = "ключ сортировки — хотя бы один столбец, уникальный последним"
            raise ValueError(message)

    def page[T: tuple[Any, ...]](
        self, statement: Select[T], after: Sequence[object] | None, limit: int
    ) -> Select[T]:
        """The statement limited to the rows after the position, plus one to see a next page."""
        if after is not None:
            if len(after) != len(self.columns):
                message = "позиция курсора не совпадает с ключом сортировки"
                raise ValueError(message)
            key, position = tuple_(*self.columns), tuple_(*after)
            statement = statement.where(key < position if self.descending else key > position)
        order = [column.desc() if self.descending else column.asc() for column in self.columns]
        return statement.order_by(*order).limit(limit + 1)

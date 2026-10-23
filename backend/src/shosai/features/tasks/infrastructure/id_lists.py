"""A list of ids as one array parameter: `column = ANY(:ids)`.

An `IN` of a whole board's cards binds one parameter per id, which PostgreSQL then plans as
a long list; one array keeps a read of a thousand cards one short statement.
"""

from collections.abc import Collection
from uuid import UUID

from sqlalchemy import ColumnElement, Uuid, any_, literal
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import InstrumentedAttribute


def among(
    column: InstrumentedAttribute[UUID] | ColumnElement[UUID], ids: Collection[UUID]
) -> ColumnElement[bool]:
    """The rows whose column holds one of the ids."""
    return column == any_(literal(list(ids), ARRAY(Uuid)))

"""A page request and a page: the query parameters and the response shape of a collection.

Every collection answers `{"items": [...], "next_cursor": "..." | null}`. A page request
is `limit` (1 … the collection's maximum, 50 … 100 by default) and an optional `cursor`;
a limit outside its bounds is a 422 before the handler runs, so no request reads an
unbounded page (§10, api-design).
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Annotated, Final

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict

from shosai.core.pagination.cursor import CURSOR_MAX_LENGTH, CursorCodec

DEFAULT_PAGE_SIZE: Final = 50
MAX_PAGE_SIZE: Final = 100


@dataclass(frozen=True, slots=True)
class PageRequest:
    """How many items to return and after which position."""

    limit: int
    cursor: str | None = None


class Page[T](BaseModel):
    """One page of a collection and the cursor of the next one, null on the last page."""

    model_config = ConfigDict(frozen=True)

    items: list[T]
    next_cursor: str | None


def page_parameters(
    default: int = DEFAULT_PAGE_SIZE, maximum: int = MAX_PAGE_SIZE
) -> Callable[..., PageRequest]:
    """The FastAPI dependency of a collection's `limit` and `cursor` query parameters."""
    if not 1 <= default <= maximum:
        message = "размер страницы по умолчанию — от 1 до максимума"
        raise ValueError(message)

    def page_request(
        limit: Annotated[
            int, Query(ge=1, le=maximum, description="Items per page, at most the maximum.")
        ] = default,
        cursor: Annotated[
            str | None,
            Query(
                max_length=CURSOR_MAX_LENGTH,
                description="The next_cursor of the previous page; absent for the first page.",
            ),
        ] = None,
    ) -> PageRequest:
        return PageRequest(limit=limit, cursor=cursor)

    return page_request


PageParameters = Annotated[PageRequest, Depends(page_parameters())]


def page_of[R, T, P: BaseModel](
    rows: Sequence[R],
    request: PageRequest,
    codec: CursorCodec[P],
    item: Callable[[R], T],
    position: Callable[[R], P],
) -> Page[T]:
    """The page of up to `limit` rows read as `limit + 1`: one more means a next page."""
    shown = rows[: request.limit]
    more = len(rows) > request.limit
    return Page(
        items=[item(row) for row in shown],
        next_cursor=codec.encode(position(shown[-1])) if more else None,
    )

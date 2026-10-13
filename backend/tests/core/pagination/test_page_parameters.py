"""A page request is bounded before the handler runs; a bad cursor is a 422 (§10)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from shosai.core.pagination.cursor import CursorCodec
from shosai.core.pagination.page import (
    MAX_PAGE_SIZE,
    Page,
    PageParameters,
    PageRequest,
    page_parameters,
)
from tests.core.web.probe_app import build_probe_app, client_of

ROUTE = "/v1/probe/pages"
SMALL_ROUTE = "/v1/probe/small-pages"


class Position(BaseModel):
    """The id the page ended at."""

    id: uuid.UUID


CODEC = CursorCodec("probe.pages", Position)
SmallPage = Annotated[PageRequest, Depends(page_parameters(default=10, maximum=20))]


def pages_router() -> APIRouter:
    """Two collections: the default bounds and a small one."""
    router = APIRouter()

    @router.get(ROUTE)
    async def list_pages(page: PageParameters) -> Page[int]:
        """Echo the bounds; decode the cursor when there is one."""
        if page.cursor is not None:
            CODEC.decode(page.cursor)
        return Page(items=[page.limit], next_cursor=None)

    @router.get(SMALL_ROUTE)
    async def list_small(page: SmallPage) -> Page[int]:
        """A collection with its own bounds."""
        return Page(items=[page.limit], next_cursor=None)

    return router


async def test_a_page_size_above_the_bound_or_below_one_is_422() -> None:
    probe = build_probe_app(extra=[pages_router()])
    async with client_of(probe.app) as client:
        default = await client.get(ROUTE)
        largest = await client.get(ROUTE, params={"limit": MAX_PAGE_SIZE})
        too_large = await client.get(ROUTE, params={"limit": MAX_PAGE_SIZE + 1})
        zero = await client.get(ROUTE, params={"limit": 0})

    assert default.json() == {"items": [50], "next_cursor": None}
    assert largest.json()["items"] == [MAX_PAGE_SIZE]
    assert (too_large.status_code, zero.status_code) == (422, 422)
    assert too_large.json()["error"]["code"] == "validation_error"


async def test_a_collection_sets_its_own_bounds_and_openapi_shows_them() -> None:
    probe = build_probe_app(extra=[pages_router()])
    async with client_of(probe.app) as client:
        default = await client.get(SMALL_ROUTE)
        too_large = await client.get(SMALL_ROUTE, params={"limit": 21})

    parameters = probe.app.openapi()["paths"][SMALL_ROUTE]["get"]["parameters"]
    [limit] = [item for item in parameters if item["name"] == "limit"]
    assert default.json()["items"] == [10]
    assert too_large.status_code == 422
    assert (limit["schema"]["maximum"], limit["schema"]["default"]) == (20, 10)


async def test_a_cursor_from_elsewhere_is_422_and_a_long_one_never_reaches_the_handler() -> None:
    probe = build_probe_app(extra=[pages_router()])
    foreign = CursorCodec("probe.other", Position).encode(Position(id=uuid.uuid7()))
    async with client_of(probe.app) as client:
        refused = await client.get(ROUTE, params={"cursor": foreign})
        long = await client.get(ROUTE, params={"cursor": "a" * 513})
        own = await client.get(ROUTE, params={"cursor": CODEC.encode(Position(id=uuid.uuid7()))})

    assert (refused.status_code, refused.json()["error"]["code"]) == (422, "invalid_cursor")
    assert long.status_code == 422
    assert own.status_code == 200

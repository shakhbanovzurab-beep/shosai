"""A share link's page and comments: `GET /v1/shared/{token}`, `GET` and `POST …/comments`.

Anyone holding the link reads them, with no account. Every link that does not open —
unknown, malformed, expired, turned off, of a hidden or not-kept meeting, of an account in
its deletion window — answers the same 404 `share_not_found`. Sixty reads and six comments
a minute per address. Other errors: `comments_closed`, `comment_invalid`, `rate_limited`.
"""

from datetime import timedelta
from http import HTTPStatus
from typing import Annotated, Final

from fastapi import APIRouter, Depends, Path

from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.web.rate_limit import rate_limited
from shosai.features.notes.application.shared_pages import SharedPages
from shosai.features.notes.channels.http.shared_shapes import (
    SharedCommentIn,
    SharedCommentOut,
    SharedCommentsOut,
    SharedMeetingOut,
    comment_out,
    page_out,
)
from shosai.features.notes.domain.sharing import COMMENTS_PER_MINUTE, VIEWS_PER_MINUTE

VIEWS: Final = RateLimit(
    "notes.shared_view", VIEWS_PER_MINUTE, timedelta(minutes=1), VIEWS_PER_MINUTE
)
COMMENTS: Final = RateLimit(
    "notes.shared_comment", COMMENTS_PER_MINUTE, timedelta(minutes=1), COMMENTS_PER_MINUTE
)
Token = Annotated[str, Path(min_length=1, max_length=128)]


def build_shared_router(pages: SharedPages, limiter: RateLimiter) -> APIRouter:
    """The pages and comments of share links."""
    router = APIRouter(prefix="/v1/shared/{token}", tags=["shared"])
    viewed = [Depends(rate_limited(limiter, VIEWS))]

    @router.get("", dependencies=viewed)
    async def get_shared_meeting(token: Token) -> SharedMeetingOut:
        """The meeting the link shares, as its settings allow."""
        return page_out(await pages.page(token))

    @router.get("/comments", dependencies=viewed)
    async def list_shared_comments(token: Token) -> SharedCommentsOut:
        """The newest comments under the page, oldest first."""
        return SharedCommentsOut(items=[comment_out(c) for c in await pages.comments(token)])

    @router.post(
        "/comments",
        status_code=HTTPStatus.CREATED,
        dependencies=[Depends(rate_limited(limiter, COMMENTS))],
    )
    async def post_shared_comment(token: Token, body: SharedCommentIn) -> SharedCommentOut:
        """Leave a comment under the page, as a name or a guest."""
        return comment_out(await pages.comment(token, body.author, body.text))

    return router

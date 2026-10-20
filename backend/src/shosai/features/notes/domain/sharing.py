"""A meeting's share link (MT-D5; the cabinet's `notes/domain/share-link.ts`; §7).

A meeting has at most one link, on or off, with four settings: show the transcript, show
names, allow comments, and expiry — never, 7, 30 or 90 days, counted from when the expiry
was last chosen. The token is 32 random bytes in base64url; it stays across changes of
the settings, and a link turned off is gone with its comments, so turning it on again
gives a new token. A link that is off, expired or of a hidden or not-kept meeting or a
hidden owner does not resolve, and every such case answers the same. Comments: an author
of at most 60 characters (none: a guest), a text of 1 to 2 000; the page shows the
newest 200.
"""

import re
import secrets
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final

TOKEN_BYTES: Final = 32
# Ссылки черновика тоже проходят: токены переносятся как есть (S-4).
TOKEN: Final = re.compile(r"[A-Za-z0-9_-]{1,64}")
COMMENT_TEXT_MAX: Final = 2000
COMMENT_AUTHOR_MAX: Final = 60
COMMENTS_SHOWN: Final = 200
VIEWS_PER_MINUTE: Final = 60
COMMENTS_PER_MINUTE: Final = 6


class ShareExpiry(StrEnum):
    """How long a link works from when its expiry was chosen."""

    NEVER = "never"
    DAYS_7 = "7d"
    DAYS_30 = "30d"
    DAYS_90 = "90d"


EXPIRY_DAYS: Final = {ShareExpiry.DAYS_7: 7, ShareExpiry.DAYS_30: 30, ShareExpiry.DAYS_90: 90}


@dataclass(frozen=True, slots=True)
class ShareSettings:
    """What the link's page shows and allows."""

    show_transcript: bool = True
    show_names: bool = False
    allow_comments: bool = False
    expiry: ShareExpiry = ShareExpiry.NEVER


def new_token() -> str:
    """A fresh link token: 32 random bytes, 43 base64url characters."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def well_formed(token: str) -> bool:
    """Whether a token may name a link at all; anything else is refused before any lookup."""
    return TOKEN.fullmatch(token) is not None


def expires_at(expiry: ShareExpiry, chosen_at: datetime) -> datetime | None:
    """When a link whose expiry was chosen at `chosen_at` stops working."""
    days = EXPIRY_DAYS.get(expiry)
    return None if days is None else chosen_at + timedelta(days=days)


def next_expires_at(
    previous: ShareSettings | None,
    settings: ShareSettings,
    current: datetime | None,
    now: datetime,
) -> datetime | None:
    """A link's end after a change: counted anew only when its expiry was chosen anew."""
    if previous is not None and previous.expiry is settings.expiry:
        return current
    return expires_at(settings.expiry, now)


@dataclass(frozen=True, slots=True)
class LinkState:
    """What decides whether a link resolves."""

    expires_at: datetime | None
    meeting_hidden: bool = False
    meeting_kept: bool = True
    owner_hidden: bool = False


def resolves(state: LinkState, now: datetime) -> bool:
    """Whether the link's page opens; every refusal looks the same to the reader."""
    expired = state.expires_at is not None and state.expires_at <= now
    return state.meeting_kept and not (expired or state.meeting_hidden or state.owner_hidden)


class CommentRuleError(ValueError):
    """A comment breaks a rule (422 `comment_invalid`)."""

    code = "comment_invalid"

    def __init__(self) -> None:
        super().__init__(self.code)


def _clean(raw: str) -> str:
    return "".join(c for c in raw if c in "\n\t" or unicodedata.category(c) != "Cc").strip()


def checked_comment(author: str | None, text: str) -> tuple[str | None, str]:
    """The comment's author (None: a guest) and its text, or the rule it breaks."""
    clean_text = _clean(text)
    clean_author = " ".join(_clean(author or "").split()) or None
    if not clean_text or len(clean_text) > COMMENT_TEXT_MAX:
        raise CommentRuleError
    if clean_author is not None and len(clean_author) > COMMENT_AUTHOR_MAX:
        raise CommentRuleError
    return clean_author, clean_text

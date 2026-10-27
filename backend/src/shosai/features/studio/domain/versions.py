"""Publishing the platform layer: numbered immutable versions, restore as a new version.

The operator's draft is published whole, cleaned and checked, as the next number; a draft
equal to what is live — the built-in empty layer before the first publish — has nothing to
publish. Restoring an old version publishes a copy of it as the next number, checked again
by today's rules, and resets the draft to it; its comment may be empty, and the screen then
words it from `restored_from`. History is never rewritten.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from shosai.features.studio.domain.errors import StudioRule, StudioRuleError
from shosai.features.studio.domain.platform_layer import (
    BUILT_IN,
    PlatformConfig,
    check_publishable,
    cleaned,
)

COMMENT_MAX: Final = 280


@dataclass(frozen=True, slots=True)
class Version:
    """One published version of the platform layer."""

    id: UUID
    number: int
    config: PlatformConfig
    comment: str
    published_at: datetime
    restored_from: int | None = None


@dataclass(frozen=True, slots=True)
class Publication:
    """What a publish or a restore writes: the number, the config and its comment."""

    number: int
    config: PlatformConfig
    comment: str
    restored_from: int | None = None


def next_number(latest: int | None) -> int:
    """The number of the next version: 1 before the first."""
    return 1 if latest is None else latest + 1


def checked_comment(comment: str, *, required: bool) -> str:
    """The comment trimmed; a publish needs one, a restore may leave it empty."""
    text = comment.strip()
    if required and not text:
        message = "комментарий к публикации обязателен: схема пропустила пустой"
        raise ValueError(message)
    if len(text) > COMMENT_MAX:
        message = f"комментарий длиннее {COMMENT_MAX}: схема пропустила длинный"
        raise ValueError(message)
    return text


def publication(draft: PlatformConfig, live: Version | None, comment: str) -> Publication:
    """The draft as the next version, or the reason it cannot be published."""
    config = cleaned(draft)
    if config == (live.config if live is not None else BUILT_IN):
        raise StudioRuleError(StudioRule.NOTHING_TO_PUBLISH)
    check_publishable(config)
    number = next_number(live.number if live is not None else None)
    return Publication(number, config, checked_comment(comment, required=True))


def restoration(old: Version, live: Version, comment: str) -> Publication:
    """A copy of an old version as the next one, checked by today's rules; the live one's
    own copy has nothing to publish."""
    config = cleaned(old.config)
    if config == live.config:
        raise StudioRuleError(StudioRule.NOTHING_TO_PUBLISH)
    check_publishable(config)
    return Publication(
        next_number(live.number), config, checked_comment(comment, required=False), old.number
    )

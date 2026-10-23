"""A task made from a team chat (TK-D13, tasks plan §3.10).

A chat task is a workspace's task Leo made from a message of one of the workspace's chats —
a chat command's run or a digest's item. It keeps the chat as it was named and the message's
moment and link, never the message's text or author: those stay in the messenger and in
chats' store. The connection goes once the chat is disconnected; the line stays. A Telegram
basic group has no message links, so the link may be absent.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Final
from uuid import UUID

from shosai.features.tasks.domain.tasks import TaskRule, TaskRuleError

CHAT_TITLE_MAX: Final = 255
MESSAGE_LINK_MAX: Final = 2048


class Messenger(StrEnum):
    """A messenger a team chat lives in (chats §1.1)."""

    TELEGRAM = "telegram"
    SLACK = "slack"


@dataclass(frozen=True, slots=True)
class ChatLine:
    """The chat a card names on its face."""

    messenger: Messenger
    chat_title: str


@dataclass(frozen=True, slots=True)
class ChatOrigin:
    """The chat and the message a task was made from."""

    connection_id: UUID | None
    messenger: Messenger
    chat_title: str
    message_url: str | None
    message_at: datetime


def checked_origin(origin: ChatOrigin) -> ChatOrigin:
    """The origin with its chat's title trimmed to 1 to 255 characters and a link of at most
    2 048; anything else breaks the task's rules."""
    title = origin.chat_title.strip()
    link = origin.message_url
    if not 1 <= len(title) <= CHAT_TITLE_MAX or (link is not None and len(link) > MESSAGE_LINK_MAX):
        raise TaskRuleError(TaskRule.INVALID)
    return replace(origin, chat_title=title)

"""The call's chat: kept with the meeting, relayed by the server (MR-D11).

A participant sends a message to meetings' route, which checks the ban and the rate (20 per
10 s per principal), keeps it for the call with the next `seq` and publishes it to the room
reliably on topic `chat`. Each message has an id and a sequence: a client drops what it has
already seen by id and asks for what it missed after the last `seq` it holds. The author is
the name the pass was issued with. At the call's end the chat passes to notes with the
meeting (B3); a call with notes off keeps none of it.
"""

import json
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final
from uuid import UUID

TEXT_MAX: Final = 2_000
RATE_COUNT: Final = 20
RATE_WINDOW_SECONDS: Final = 10
# Сколько сообщений отдаёт одна страница истории; столько же держит панель клиента.
HISTORY_PAGE_MAX: Final = 200
TOPIC: Final = "chat"
PAYLOAD_VERSION: Final = 1
# Перевод строки и табуляция — часть текста; прочие управляющие символы выбрасываются.
KEPT_CONTROLS: Final = frozenset("\n\t")


class ChatRule(StrEnum):
    """A rule of the chat; the value is the API's error code."""

    TEXT_REQUIRED = "text_required"
    TEXT_TOO_LONG = "text_too_long"


class ChatRuleError(ValueError):
    """A message breaks a rule."""

    def __init__(self, rule: ChatRule) -> None:
        super().__init__(rule.value)
        self.rule = rule
        self.code = rule.value


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """A message of a call as kept and as published."""

    id: UUID
    call_id: UUID
    seq: int
    # Принципал автора и личность его сессии: клиент отмечает свои сообщения.
    principal: str
    identity: str
    author: str
    text: str
    sent_at: datetime

    def __post_init__(self) -> None:
        if self.seq < 1:
            message = "seq сообщения чата — с единицы"
            raise ValueError(message)


def checked_text(raw: str) -> str:
    """The message's text: control characters but line breaks and tabs dropped, trimmed, 1 to
    2 000 characters."""
    text = "".join(
        ch for ch in raw if ch in KEPT_CONTROLS or unicodedata.category(ch) != "Cc"
    ).strip()
    if not text:
        raise ChatRuleError(ChatRule.TEXT_REQUIRED)
    if len(text) > TEXT_MAX:
        raise ChatRuleError(ChatRule.TEXT_TOO_LONG)
    return text


def next_seq(last_seq: int | None) -> int:
    """The sequence of the call's next message: one after the last, from one."""
    return 1 if last_seq is None else last_seq + 1


def payload(message: ChatMessage) -> bytes:
    """The data packet published on topic `chat`: compact JSON, versioned."""
    body = {
        "v": PAYLOAD_VERSION,
        "id": str(message.id),
        "seq": message.seq,
        "identity": message.identity,
        "author": message.author,
        "text": message.text,
        "sent_at": message.sent_at.isoformat(),
    }
    return json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()

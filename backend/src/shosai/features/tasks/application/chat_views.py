"""The team chat a task came from, as a read shows it (TK-D13, tasks plan §3.10).

A card names the messenger and the chat; the panel adds the connection, while the chat is
connected, and the message's moment and link. They are columns of the task's row, read
with it; a task from anywhere else has none.
"""

from shosai.features.tasks.application.task_parts import CardFacts
from shosai.features.tasks.domain.chat_source import ChatLine, ChatOrigin, Messenger
from shosai.features.tasks.infrastructure.task_records import TaskRecord


def chat_line_of(record: CardFacts) -> ChatLine | None:
    """The chat a card names, if the task came from one."""
    messenger, title = record.source_chat_messenger, record.source_chat_title
    return None if messenger is None or title is None else ChatLine(Messenger(messenger), title)


def chat_origin_of(record: TaskRecord) -> ChatOrigin | None:
    """The chat and the message the task came from, if it came from one."""
    messenger, title, at = (
        record.source_chat_messenger, record.source_chat_title, record.source_chat_message_at,
    )  # fmt: skip
    if messenger is None or title is None or at is None:
        return None
    return ChatOrigin(
        record.source_chat_connection_id, Messenger(messenger), title,
        record.source_chat_message_url, at,
    )  # fmt: skip

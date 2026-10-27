"""The call's chat: its text, its sequence and its packet (MR-D11)."""

import json
import uuid
from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.meetings.domain.chat import (
    RATE_COUNT,
    RATE_WINDOW_SECONDS,
    TEXT_MAX,
    TOPIC,
    ChatMessage,
    ChatRuleError,
    checked_text,
    next_seq,
    payload,
)

SENT = datetime(2026, 10, 27, 12, 30, tzinfo=UTC)


def message(seq: int = 1, text: str = "Ссылка: https://shosai.tech") -> ChatMessage:
    return ChatMessage(
        id=uuid.uuid4(),
        call_id=uuid.uuid4(),
        seq=seq,
        principal="guest-0123456789ab",
        identity="guest-0123456789ab__0a1b2c3d",
        author="Анна",
        text=text,
        sent_at=SENT,
    )


def test_text_keeps_line_breaks_and_drops_other_controls() -> None:
    assert checked_text("  первая\nвторая\tстрока\x07 ") == "первая\nвторая\tстрока"
    assert checked_text("مرحبا") == "مرحبا"


@pytest.mark.parametrize(
    ("raw", "code"), [(" \n\t ", "text_required"), ("я" * (TEXT_MAX + 1), "text_too_long")]
)
def test_text_breaks_its_rules(raw: str, code: str) -> None:
    with pytest.raises(ChatRuleError) as error:
        checked_text(raw)
    assert error.value.code == code


@given(st.text(max_size=3_000))
def test_checked_text_is_bounded_trimmed_and_stable(raw: str) -> None:
    try:
        text = checked_text(raw)
    except ChatRuleError:
        return
    assert 1 <= len(text) <= TEXT_MAX
    assert text == text.strip()
    assert checked_text(text) == text


def test_the_sequence_starts_at_one_and_grows_by_one() -> None:
    assert next_seq(None) == 1
    assert next_seq(41) == 42
    with pytest.raises(ValueError, match="seq"):
        message(seq=0)


def test_the_packet_on_topic_chat_is_versioned_json_with_id_and_seq() -> None:
    sent = message(seq=7)
    body = json.loads(payload(sent))

    assert TOPIC == "chat"
    assert body == {
        "v": 1,
        "id": str(sent.id),
        "seq": 7,
        "identity": "guest-0123456789ab__0a1b2c3d",
        "author": "Анна",
        "text": "Ссылка: https://shosai.tech",
        "sent_at": "2026-10-27T12:30:00+00:00",
    }
    assert (RATE_COUNT, RATE_WINDOW_SECONDS) == (20, 10)

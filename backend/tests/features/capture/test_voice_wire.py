"""The voice wire's `hello` and an exchange's words (LEO-voice step 5, ADR 0070 LV-D2, LV-D5)."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.capture.domain.exchanges import Exchange
from shosai.features.capture.domain.voice import (
    PATH_MAX,
    MalformedHelloError,
    VoicePlace,
    voice_place,
)

AT = datetime(2026, 10, 27, 12, tzinfo=UTC)
WORKSPACE = uuid.uuid4()
THREAD = uuid.uuid4()


def test_hello_names_personal_or_a_workspace_the_thread_the_page_and_the_language() -> None:
    personal = voice_place({"scope": {"kind": "personal"}, "thread_id": None})
    workspace = voice_place(
        {
            "scope": {"kind": "workspace", "workspace_id": str(WORKSPACE)},
            "thread_id": str(THREAD),
            "path": "/app/notes/" + "x" * 600,
            "locale": "pt-BR",
        }
    )

    assert personal == VoicePlace(None, None, None, None)
    assert (workspace.workspace_id, workspace.thread_id, workspace.locale) == (
        WORKSPACE, THREAD, "pt-BR",
    )  # fmt: skip
    assert workspace.path is not None
    assert len(workspace.path) == PATH_MAX


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"scope": "personal"},
        {"scope": {"kind": "hub"}},
        {"scope": {"kind": "workspace"}},
        {"scope": {"kind": "workspace", "workspace_id": "not-a-uuid"}},
        {"scope": {"kind": "personal"}, "thread_id": 7},
        {"scope": {"kind": "personal"}, "thread_id": "nope"},
        {"scope": {"kind": "personal"}, "path": "app"},
        {"scope": {"kind": "personal"}, "locale": ""},
        {"scope": {"kind": "personal"}, "locale": "x" * 36},
    ],
)
def test_a_malformed_hello_is_refused(fields: dict[str, Any]) -> None:
    with pytest.raises(MalformedHelloError):
        voice_place(fields)


def test_an_exchange_gathers_both_sides_and_what_the_person_said_over_leo_opens_the_next() -> None:
    exchange = Exchange()
    exchange.hear(" What about", AT, final=False)
    exchange.hear(" the budget?", AT, final=True)
    exchange.call(AT)
    exchange.say(" Travel was cut", AT)
    exchange.say(" by a fifth.", AT)
    over = exchange.hear(" And hotels?", AT, final=False)
    following = exchange.following(AT)

    assert (exchange.question, exchange.answer) == (
        "What about the budget?",
        "Travel was cut by a fifth.",
    )
    assert exchange.answered
    assert over.text == "And hotels?"
    assert (following.question, following.started_at, following.answered) == (
        "And hotels?",
        AT,
        False,
    )
    assert exchange.started_at == AT


def test_a_phrase_still_open_takes_the_persons_words_even_while_leo_speaks() -> None:
    exchange = Exchange()
    exchange.hear("Remind me", AT, final=False)
    exchange.say("Sure", AT)
    exchange.hear(" to call Anna.", AT, final=True)

    assert exchange.question == "Remind me to call Anna."
    assert exchange.following(AT).empty


@given(st.lists(st.text(max_size=8), max_size=12))
def test_the_question_is_the_persons_pieces_joined(pieces: list[str]) -> None:
    exchange = Exchange()
    for piece in pieces:
        exchange.hear(piece, AT, final=False)

    assert exchange.question == "".join(pieces).strip()
    assert exchange.empty == (not "".join(pieces).strip())

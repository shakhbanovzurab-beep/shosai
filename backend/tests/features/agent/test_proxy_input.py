"""What the native proxy takes from a shipped client (agent step 14): the newest of the
conversation within its budget, the latest always kept; the screenshots that decode, six at
most; the temperature and the output bound held to the proxy's range."""

import base64

from shosai.features.agent.domain.proxy_input import (
    ANSWER_TOKENS,
    CONVERSATION_CHARS,
    FRAME_BYTES,
    KEPT_MESSAGES,
    MESSAGE_CHARS,
    Said,
    answer_temperature,
    answer_tokens,
    frames,
    kept_conversation,
    media_type,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\0" * 16
WEBP = b"RIFF\0\0\0\0WEBPVP8 "


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def test_empty_messages_go_and_the_newest_fifty_stay_in_order() -> None:
    said = [Said("system", " "), *(Said("user", f"m{n}") for n in range(60))]

    kept = kept_conversation(said)

    assert len(kept) == KEPT_MESSAGES
    assert [m.content for m in kept[:2]] == ["m10", "m11"]
    assert kept[-1] == Said("user", "m59")


def test_the_budget_keeps_the_newest_and_never_drops_the_question() -> None:
    long = "x" * (CONVERSATION_CHARS // 2)
    said = [Said("user", "old"), Said("assistant", long), Said("user", long + "?")]
    huge = [Said("system", "rules"), Said("user", "y" * (MESSAGE_CHARS + 10))]

    kept = kept_conversation(said)
    alone = kept_conversation(huge)

    assert [m.role for m in kept] == ["user"]
    assert kept[0].content.endswith("?")
    assert [len(m.content) for m in alone] == [len("rules"), MESSAGE_CHARS]


def test_frames_decode_strictly_six_at_most_with_or_without_a_data_prefix() -> None:
    images = [
        f"data:image/png;base64,{b64(PNG)}", "not base64!", b64(JPEG) + "\n", "",
        *(b64(JPEG) for _ in range(8)),
    ]  # fmt: skip
    oversized = "A" * (FRAME_BYTES * 4 // 3 + 8)

    found = frames(images, "")

    assert found[0] == PNG
    assert len(found) == 6
    assert frames(None, b64(PNG)) == [PNG]
    assert frames([], "") == []
    assert frames([oversized], "") == []


def test_a_frame_s_type_is_read_from_its_first_bytes() -> None:
    assert [media_type(frame) for frame in (PNG, JPEG, b"GIF89a..", WEBP, b"??")] == [
        "image/png", "image/jpeg", "image/gif", "image/webp", "image/png",
    ]  # fmt: skip


def test_temperature_and_tokens_are_held_to_the_proxy_s_range() -> None:
    assert [answer_temperature(t) for t in (None, -1.0, 0.7, 9.0)] == [None, 0.0, 0.7, 2.0]
    assert [answer_tokens(n) for n in (None, 1, 32_768)] == [ANSWER_TOKENS, 1, ANSWER_TOKENS]

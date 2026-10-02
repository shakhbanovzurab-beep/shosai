"""Object keys: the draft's keys pass, anything that could escape a prefix does not."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from whisperer.core.storage.keys import check_object_key, check_prefix, check_root

SEGMENTS = st.text(st.characters(codec="utf-8", exclude_categories=("Cs", "Cc")), min_size=1)


@pytest.mark.parametrize(
    "key",
    [
        "u-0f3a2b1c/5b6e8a7d-1c2d-4e5f-8a9b-0c1d2e3f4a5b/%D0%BE%D1%82%D1%87%D1%91%D1%82.pdf",
        "platform/builds/whisperer-1.4.5.dmg",
        "o-7/meetings/2026/10/audio.webm",
        "отчёт за октябрь.pdf",
    ],
)
def test_draft_and_v2_keys_pass(key: str) -> None:
    assert check_object_key(key) == key


@pytest.mark.parametrize(
    "key",
    ["", "/u-1/a.pdf", "u-1//a.pdf", "u-1/../u-2/a.pdf", "u-1/./a", "u-1/a/", "a\\b", "a\x00b"],
)
def test_keys_that_could_escape_or_break_a_url_are_refused(key: str) -> None:
    with pytest.raises(ValueError, match="ключ объекта"):
        check_object_key(key)


@given(st.lists(SEGMENTS, min_size=1, max_size=4), st.sampled_from(["..", "."]))
def test_a_dot_segment_anywhere_is_refused(segments: list[str], dots: str) -> None:
    key = "/".join([*segments, dots, *segments])

    with pytest.raises(ValueError, match="ключ объекта"):
        check_object_key(key)


def test_a_key_over_1024_bytes_is_refused() -> None:
    check_object_key("я" * 512)

    with pytest.raises(ValueError, match="1024 байт"):
        check_object_key("я" * 513)


def test_prefixes_and_roots() -> None:
    assert check_prefix("") == ""
    assert check_prefix("u-1/") == "u-1/"
    assert check_prefix("u-1/rec") == "u-1/rec"
    assert check_root("tests/slot-3/") == "tests/slot-3/"
    with pytest.raises(ValueError, match="корневой префикс"):
        check_root("tests/slot-3")
    with pytest.raises(ValueError, match="ключ объекта"):
        check_prefix("../")

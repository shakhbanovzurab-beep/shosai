"""Key layout: `shosai:<purpose>:<part>…`, parts from a closed alphabet."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.core.kv.keys import KEY_PART, build_key


def test_parts_join_under_the_project_prefix() -> None:
    assert build_key("lock", "relay.ru") == "shosai:lock:relay.ru"
    assert build_key("rate", "sign_in", "0f3a") == "shosai:rate:sign_in:0f3a"


@given(st.text(max_size=140).filter(lambda part: not KEY_PART.fullmatch(part)))
def test_a_part_outside_the_alphabet_is_refused_without_echo(part: str) -> None:
    with pytest.raises(ValueError, match="часть ключа") as raised:
        build_key("cache", part)
    with pytest.raises(ValueError, match="часть ключа") as reference:
        build_key("cache", "@")

    # Сообщение одно на все отказы: часть ключа в него не попадает.
    assert str(raised.value) == str(reference.value)


@pytest.mark.parametrize("part", ["a:b", "user@example.com", "*", "x y", "", "z" * 129])
def test_separators_globs_and_free_text_are_refused(part: str) -> None:
    with pytest.raises(ValueError, match="часть ключа"):
        build_key("lock", part)

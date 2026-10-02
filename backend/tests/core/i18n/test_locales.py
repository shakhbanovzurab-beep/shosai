"""The 16 platform languages and the language a request prefers."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from whisperer.core.i18n.locales import (
    LOCALES,
    SUPPORTED_LANGUAGES,
    normalize_language,
    parse_accept_language,
)


def test_sixteen_languages_with_unique_codes() -> None:
    assert len(LOCALES) == 16
    assert len(set(SUPPORTED_LANGUAGES)) == 16
    assert SUPPORTED_LANGUAGES[:4] == ("en", "zh", "es", "ru")
    assert [locale.code for locale in LOCALES if locale.rtl] == ["ar"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("ru", "ru"),
        ("pt-BR", "pt"),
        ("zh_Hant", "zh"),
        (" DE ", "de"),
        ("xx", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_language(value: str | None, expected: str | None) -> None:
    assert normalize_language(value) == expected


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7", "ru"),
        ("de;q=0.5, fr", "fr"),
        ("xx-YY, en;q=0.1", "en"),
        ("es;q=0.8, it;q=0.8", "es"),
        ("ru;q=0, en", "en"),
        ("ja;q=abc, ko;q=0.2", "ko"),
        ("vi;q=1.5, th;q=0.3", "th"),
        ("*", None),
        ("xx, yy", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_accept_language(header: str | None, expected: str | None) -> None:
    assert parse_accept_language(header) == expected


@given(st.text(max_size=200))
def test_any_header_gives_a_supported_language_or_none(header: str) -> None:
    assert parse_accept_language(header) in {*SUPPORTED_LANGUAGES, None}

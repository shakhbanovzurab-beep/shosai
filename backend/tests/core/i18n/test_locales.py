"""The 16 platform languages and the language a request prefers."""

import re
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.core.i18n.locales import (
    LOCALES,
    SUPPORTED_LANGUAGES,
    normalize_language,
    parse_accept_language,
)

CABINET_LANGUAGES = Path(__file__).resolve().parents[4] / "frontend/src/lib/language.ts"


def test_sixteen_languages_with_unique_codes() -> None:
    assert len(LOCALES) == 16
    assert len(set(SUPPORTED_LANGUAGES)) == 16
    assert [locale.code for locale in LOCALES if locale.rtl] == ["ar"]


def test_the_platform_speaks_the_cabinets_languages_with_its_codes() -> None:
    cabinet = re.findall(r'\{ code: "([^"]+)"', CABINET_LANGUAGES.read_text(encoding="utf-8"))

    assert tuple(cabinet) == SUPPORTED_LANGUAGES


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("ru", "ru"),
        ("pt-BR", "pt-BR"),
        ("pt", "pt-BR"),
        ("pt_br", "pt-BR"),
        ("zh_Hant", "zh-Hant"),
        ("zh-TW", "zh-Hant"),
        ("nl-BE", "nl"),
        (" DE ", "de"),
        ("th", None),
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
        ("vi;q=1.5, nl;q=0.3", "nl"),
        ("th-TH, pt-PT;q=0.5", "pt-BR"),
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

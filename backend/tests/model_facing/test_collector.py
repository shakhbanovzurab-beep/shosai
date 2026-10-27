"""The model-facing check catches non-English instructions in every kind of source."""

from collections.abc import Iterable
from enum import StrEnum

import pytest
from pydantic import BaseModel, Field, create_model

from shosai.core.kernel.latin_script import non_latin_letters
from tests.model_facing.collector import find_violations, iter_texts
from tests.model_facing.registry import ModelFacingSource


class Tone(StrEnum):
    """Enum values end up in a tool schema, where a model sees them."""

    CALM = "calm"
    BRIEF = "кратко"


class SearchArguments(BaseModel):
    """Arguments of a sample search tool."""

    query: str = Field(description="Строка поиска")


class SearchResult(BaseModel):
    """Result of a sample search tool."""

    status: str


# Докстринг модели Pydantic становится описанием её JSON-схемы, которое читает
# модель. Образец с русским описанием собирается динамически: докстринги в коде
# пишутся только по-английски, и это проверяет test_docstrings_english.
SearchFilters = create_model(
    "SearchFilters",
    __doc__="Фильтры поиска.",
    folder=(str, Field(description="Folder to search in")),
)


def violations_of(*values: object, allowed: Iterable[str] = ()) -> list[str]:
    source = ModelFacingSource(
        owner="harness",
        name="sample",
        collect=lambda: values,
        allowed_literals=frozenset(allowed),
    )
    return find_violations([source])


def test_a_russian_instruction_fails() -> None:
    violations = violations_of("Отвечай кратко и по делу.")

    assert len(violations) == 1
    assert violations[0].startswith("harness / sample $:")


def test_english_with_latin_diacritics_passes() -> None:
    assert violations_of("Answer briefly. Naïve café résumé, 42 %, «quotes» — fine.") == []


def test_a_declared_endonym_passes_and_an_undeclared_one_fails() -> None:
    languages = {"languages": ["English", "Русский", "日本語"]}

    assert violations_of(languages, allowed={"Русский", "日本語"}) == []
    assert len(violations_of(languages, allowed={"Русский"})) == 1


def test_enum_values_are_checked() -> None:
    violations = violations_of(Tone)

    assert len(violations) == 1
    assert "Tone.BRIEF" in violations[0]


def test_pydantic_schemas_and_results_are_checked() -> None:
    assert len(violations_of(SearchArguments)) == 1
    assert "SearchFilters schema>['description']" in violations_of(SearchFilters)[0]
    assert len(violations_of(SearchResult(status="найдено"))) == 1
    assert violations_of(SearchResult(status="found")) == []


def test_tool_schema_keys_and_nested_values_are_checked() -> None:
    schema = {"name": "search", "parameters": {"запрос": {"type": "string"}}}

    texts = [item.text for item in iter_texts(schema)]

    assert "запрос" in texts
    assert len(violations_of(schema)) == 1


def test_a_cycle_is_walked_once() -> None:
    looped: list[object] = ["text"]
    looped.append(looped)

    assert [item.text for item in iter_texts(looped)] == ["text"]


def test_an_unsupported_object_is_rejected() -> None:
    with pytest.raises(TypeError, match="object не поддерживается"):
        list(iter_texts(object()))


@pytest.mark.parametrize(
    ("text", "letters"),
    [("Hello", []), ("Привет", ["П", "в", "е", "и", "р", "т"]), ("Ωmega 3", ["Ω"])],
)
def test_non_latin_letters_are_listed_once(text: str, letters: list[str]) -> None:
    assert non_latin_letters(text) == sorted(letters)

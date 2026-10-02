"""Every docstring in `contracts/` is English (CLAUDE.md, "Language").

A letter outside the Latin script (Cyrillic, Greek, CJK) marks a non-English docstring.
Digits, punctuation and Latin letters with diacritics pass. Comments and messages for
engineers stay Russian and are not checked here.
"""

import ast
import unicodedata
from collections.abc import Iterator
from pathlib import Path

CONTRACTS = Path(__file__).resolve().parents[1]
DOCUMENTED_NODES = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
LATIN_LETTER_PREFIX = "LATIN "


def python_sources() -> Iterator[Path]:
    """Every Python file of the project, outside hidden directories."""
    for path in sorted(CONTRACTS.rglob("*.py")):
        if not any(part.startswith(".") for part in path.relative_to(CONTRACTS).parts):
            yield path


def docstrings(path: Path) -> Iterator[tuple[int, str]]:
    """Line and text of each module, class and function docstring in a file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, DOCUMENTED_NODES):
            text = ast.get_docstring(node, clean=False)
            if text:
                yield 1 if isinstance(node, ast.Module) else node.lineno, text


def non_latin_letters(text: str) -> list[str]:
    """Letters outside the Latin script, without repeats, in code point order."""
    return sorted(
        {
            char
            for char in text
            if char.isalpha() and not unicodedata.name(char, "").startswith(LATIN_LETTER_PREFIX)
        }
    )


def test_every_docstring_is_english() -> None:
    violations = [
        f"{path.relative_to(CONTRACTS)}:{line}: {''.join(letters)}"
        for path in python_sources()
        for line, text in docstrings(path)
        if (letters := non_latin_letters(text))
    ]

    assert violations == []


def test_the_check_sees_a_russian_docstring(tmp_path: Path) -> None:
    sample = tmp_path / "sample.py"
    sample.write_text('def sample() -> None:\n    """Пример."""\n', encoding="utf-8")

    assert [non_latin_letters(text) for _, text in docstrings(sample)] == [
        ["П", "е", "и", "м", "р"]
    ]


def test_latin_letters_with_diacritics_pass() -> None:
    assert non_latin_letters("Café, naïve, Ærø — 422 → §10") == []

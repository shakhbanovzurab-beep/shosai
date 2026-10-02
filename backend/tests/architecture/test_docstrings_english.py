"""Every docstring in the backend is English (CLAUDE.md, "Language").

Tools publish docstrings: FastAPI puts them into OpenAPI, Pydantic into JSON schemas
and agent frameworks into tool descriptions, so they follow the model-facing rule.
"""

import ast
from collections.abc import Iterator
from pathlib import Path

from tests.model_facing.collector import non_latin_letters

BACKEND = Path(__file__).resolve().parents[2]
DOCUMENTED_NODES = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def python_sources() -> Iterator[Path]:
    """Every hand-written Python file of the backend, outside hidden directories."""
    for path in sorted(BACKEND.rglob("*.py")):
        if not any(part.startswith(".") for part in path.relative_to(BACKEND).parts):
            yield path


def docstrings(path: Path) -> Iterator[tuple[int, str]]:
    """Line and text of each module, class and function docstring in a file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, DOCUMENTED_NODES):
            text = ast.get_docstring(node, clean=False)
            if text:
                yield getattr(node, "lineno", 1), text


def test_every_docstring_is_english() -> None:
    violations = [
        f"{path.relative_to(BACKEND)}:{line}: {''.join(letters)}"
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

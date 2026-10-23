"""How a write's card reads in the person's language (agent plan §3.2, ADR 0068).

A write tool's `preview` returns an i18n key with parameters (`Preview`). The slice that owns
the tool words every key it may return, in all 16 platform languages, beside the tool's spec;
the agent renders the card from that wording — a title and labelled fields whose values come
from the parameters — so every channel (the cabinet's card, the approvals inbox, later a voice
read-back or an MCP client's approval) shows the same words, and no client keeps a copy of a
slice's vocabulary. A field is a pair of a label and a value ("Tasks: 3"), so no wording
needs plural rules.
"""

import re
import string
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final

from shosai.core.agent_tools.results import Preview, PreviewParam
from shosai.core.i18n.locales import LOCALES

type Localized = Mapping[str, str]

LANGUAGES: Final = frozenset(locale.code for locale in LOCALES)
FALLBACK_LANGUAGE: Final = "en"
PREVIEW_KEY: Final = re.compile(r"agent\.[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*")
PARAM: Final = re.compile(r"[a-z][a-z0-9_]*")
TEXT_MAX: Final = 300
# Значение без слов: пустой параметр карточка не показывает вовсе.
EMPTY: Final = "—"


@dataclass(frozen=True, slots=True)
class PreviewField:
    """One row of a card: the label, and the parameter whose value it shows."""

    param: str
    label: Localized
    # Слова для значений-кодов (true/false, значения перечислений); пусто — значение как есть.
    values: Mapping[str, Localized] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PreviewWording:
    """A slice's words for one preview key: a title template and its fields."""

    key: str
    # Параметры, которые возвращает preview() с этим ключом.
    params: tuple[str, ...]
    # Шаблон с {param}; параметр с кодом (bool, перечисление) выводится словами своего поля.
    title: Localized
    fields: tuple[PreviewField, ...] = ()
    # Параметр, который карточка показывает телом как есть: текст письма, сообщения.
    body: str | None = None

    def __post_init__(self) -> None:
        problems = _wording_problems(self)
        if problems:
            message = f"формулировка превью {self.key!r}: " + "; ".join(problems)
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class RenderedPreview:
    """A card as the person reads it: its title, its rows and an optional body."""

    title: str
    fields: tuple[tuple[str, str], ...]
    body: str | None = None


def render_preview(wording: PreviewWording, preview: Preview, language: str) -> RenderedPreview:
    """The card in the language, English when the language is not one of the platform's."""
    if preview.key != wording.key:
        message = f"превью {preview.key!r} рендерится формулировкой {wording.key!r}"
        raise ValueError(message)
    code = language if language in LANGUAGES else FALLBACK_LANGUAGE
    by_param = {row.param: row for row in wording.fields}
    words = {
        name: _value_words(preview.params.get(name), by_param.get(name), code)
        for name in wording.params
    }
    rows = tuple(
        (row.label[code], words[row.param])
        for row in wording.fields
        if preview.params.get(row.param) is not None
    )
    body = preview.params.get(wording.body) if wording.body is not None else None
    return RenderedPreview(
        title=wording.title[code].format_map(words),
        fields=rows,
        body=str(body) if body is not None else None,
    )


def _value_words(value: PreviewParam, row: PreviewField | None, code: str) -> str:
    if value is None:
        return EMPTY
    raw = str(value).lower() if isinstance(value, bool) else str(value)
    if row is not None and raw in row.values:
        return row.values[raw][code]
    return raw


def _wording_problems(wording: PreviewWording) -> list[str]:
    problems: list[str] = []
    if not PREVIEW_KEY.fullmatch(wording.key):
        problems.append("ключ — agent.<срез>.<имя> в snake_case")
    params = set(wording.params)
    if len(params) != len(wording.params) or not all(PARAM.fullmatch(p) for p in params):
        problems.append("параметры — разные имена в snake_case")
    problems.extend(_localized_problems("заголовок", wording.title))
    unknown = {name for text in wording.title.values() for name in _placeholders(text)} - params
    if unknown:
        problems.append(f"заголовок ссылается на необъявленные параметры {sorted(unknown)}")
    for row in wording.fields:
        if row.param not in params:
            problems.append(f"поле {row.param!r} не объявлено в параметрах")
        problems.extend(_localized_problems(f"подпись {row.param}", row.label))
        for code_value, words in row.values.items():
            problems.extend(_localized_problems(f"значение {row.param}={code_value}", words))
    if wording.body is not None and wording.body not in params:
        problems.append("тело — один из объявленных параметров")
    return problems


def _localized_problems(what: str, texts: Localized) -> list[str]:
    problems: list[str] = []
    if set(texts) != LANGUAGES:
        missing = sorted(LANGUAGES - set(texts))
        extra = sorted(set(texts) - LANGUAGES)
        problems.append(f"{what}: нет языков {missing}, лишние {extra}")
    if any(not text.strip() or len(text) > TEXT_MAX for text in texts.values()):
        problems.append(f"{what}: текст от 1 до {TEXT_MAX} символов")
    return problems


def _placeholders(template: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(template) if name is not None}

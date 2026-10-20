"""The native answers' words are the cabinet's own translations, in every platform language."""

import json
from pathlib import Path

from shosai.core.i18n.locales import LOCALES
from shosai.features.notes.channels.http.native_words import load_native_words
from shosai.features.notes.domain.templates import BUILTIN_TEMPLATES, SectionKind

MESSAGES = Path(__file__).parents[4] / "frontend" / "src" / "i18n" / "messages"
SECTION_KEYS = {
    SectionKind.SUMMARY: "summary", SectionKind.KEY_POINTS: "keyPoints",
    SectionKind.DECISIONS: "decisions", SectionKind.ACTION_ITEMS: "actionItems",
}  # fmt: skip


def cabinet(language: str, name: str) -> dict[str, object]:
    found: dict[str, object] = json.loads((MESSAGES / language / name).read_text("utf-8"))
    return found


def test_each_word_equals_the_cabinet_s_in_every_language() -> None:
    words = load_native_words()

    assert set(words.by_language) == {locale.code for locale in LOCALES}
    for code, own in words.by_language.items():
        share, templates = cabinet(code, "notesShare.json"), cabinet(code, "notesTemplates.json")
        page = share["page"]
        sections, headings = templates["sections"], templates["headings"]
        assert isinstance(page, dict)
        assert isinstance(sections, dict)
        assert own.speaker == str(page["speaker"]).replace("{order, number}", "{n}")
        assert own.sections == {kind.value: sections[key] for kind, key in SECTION_KEYS.items()}
        assert own.headings == headings


def test_every_shipped_heading_has_its_words() -> None:
    words = load_native_words()
    codes = {section.heading for template in BUILTIN_TEMPLATES for section in template.sections}

    assert codes <= set(words.of("ja").headings)
    assert words.heading("pt", "nextSteps") == words.of("pt-BR").headings["nextSteps"]
    assert words.heading("xx", SectionKind.KEY_POINTS.value) == "Key points"
    assert words.speaker("ar", 3).endswith("3")

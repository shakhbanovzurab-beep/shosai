"""The 16 platform languages and Accept-Language parsing.

The list mirrors the frontend's locale list. Endonyms are language names in their own
language: legitimate non-Latin values, not instructions (CLAUDE.md "Prompts").
"""

from dataclasses import dataclass

QUALITY_PARAMETER = "q"
WILDCARD = "*"


@dataclass(frozen=True, slots=True)
class Locale:
    """A supported language: its code, endonym and direction."""

    code: str
    endonym: str
    rtl: bool = False


# Порядок и коды — как в меню кабинета (frontend/src/lib/language.ts, ADR 0046).
LOCALES: tuple[Locale, ...] = (
    Locale("en", "English"),
    Locale("fr", "Français"),
    Locale("de", "Deutsch"),
    Locale("ru", "Русский"),
    Locale("nl", "Nederlands"),
    Locale("it", "Italiano"),
    Locale("es", "Español"),
    Locale("pt-BR", "Português (Brasil)"),
    Locale("ar", "العربية", rtl=True),
    Locale("tr", "Türkçe"),
    Locale("ko", "한국어"),
    Locale("hi", "हिन्दी"),
    Locale("vi", "Tiếng Việt"),
    Locale("zh-Hant", "繁體中文"),
    Locale("ja", "日本語"),
    Locale("id", "Bahasa Indonesia"),
)
LOCALE_BY_CODE = {locale.code: locale for locale in LOCALES}
SUPPORTED_LANGUAGES = tuple(LOCALE_BY_CODE)
# У каждого языка платформы один вариант, поэтому любой тег языка сводится к нему по основе.
_CODE_BY_BASE = {locale.code.split("-", 1)[0].lower(): locale.code for locale in LOCALES}


def normalize_language(value: str | None) -> str | None:
    """The platform code of a language tag: `pt`, `pt_br` → `pt-BR`; `zh-TW` → `zh-Hant`.

    A language outside the 16 → None.
    """
    if not value:
        return None
    base = value.strip().lower().replace("_", "-").split("-", 1)[0]
    return _CODE_BY_BASE.get(base)


def parse_accept_language(header: str | None) -> str | None:
    """The most preferred supported language of an Accept-Language header, or None.

    Ranges are ordered by their `q` weight, ties by their order in the header. A range
    with `q=0` or a malformed weight is not acceptable (RFC 9110 §12.4.2); `*` names no
    language.
    """
    if not header:
        return None
    ranked: list[tuple[float, int, str]] = []
    for position, item in enumerate(header.split(",")):
        tag, quality = _language_range(item)
        if tag and tag != WILDCARD and quality > 0:
            ranked.append((-quality, position, tag))
    for _, _, tag in sorted(ranked):
        language = normalize_language(tag)
        if language:
            return language
    return None


def _language_range(item: str) -> tuple[str, float]:
    tag, *parameters = (part.strip() for part in item.split(";"))
    quality = 1.0
    for parameter in parameters:
        name, _, value = parameter.partition("=")
        if name.strip().lower() == QUALITY_PARAMETER:
            quality = _quality(value.strip())
    return tag, quality


def _quality(value: str) -> float:
    try:
        quality = float(value)
    except ValueError:
        return 0.0
    return quality if 0.0 <= quality <= 1.0 else 0.0

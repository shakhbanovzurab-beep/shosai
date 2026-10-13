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


LOCALES: tuple[Locale, ...] = (
    Locale("en", "English"),
    Locale("zh", "中文（繁體）"),
    Locale("es", "Español"),
    Locale("ru", "Русский"),
    Locale("hi", "हिन्दी"),
    Locale("ar", "العربية", rtl=True),
    Locale("pt", "Português"),
    Locale("fr", "Français"),
    Locale("it", "Italiano"),
    Locale("de", "Deutsch"),
    Locale("ja", "日本語"),
    Locale("ko", "한국어"),
    Locale("id", "Bahasa Indonesia"),
    Locale("tr", "Türkçe"),
    Locale("vi", "Tiếng Việt"),
    Locale("th", "ไทย"),
)
LOCALE_BY_CODE = {locale.code: locale for locale in LOCALES}
SUPPORTED_LANGUAGES = tuple(LOCALE_BY_CODE)


def normalize_language(value: str | None) -> str | None:
    """`pt-BR` → `pt`, `zh_Hant` → `zh`; a language outside the 16 → None."""
    if not value:
        return None
    base = value.strip().lower().replace("_", "-").split("-", 1)[0]
    return base if base in LOCALE_BY_CODE else None


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

"""The 16 platform languages and Accept-Language parsing.

The list mirrors the frontend's locale list. Endonyms are language names in their own
language: legitimate non-Latin values, not instructions (CLAUDE.md "Prompts").
"""

from dataclasses import dataclass

QUALITY_PARAMETER = "q"
WILDCARD = "*"


@dataclass(frozen=True, slots=True)
class Locale:
    """A supported language: its code, BCP 47 tag, endonym, Open Graph locale and direction."""

    code: str
    hreflang: str
    endonym: str
    og_locale: str
    rtl: bool = False


LOCALES: tuple[Locale, ...] = (
    Locale("en", "en", "English", "en_US"),
    Locale("zh", "zh-Hant", "中文（繁體）", "zh_TW"),
    Locale("es", "es", "Español", "es_ES"),
    Locale("ru", "ru", "Русский", "ru_RU"),
    Locale("hi", "hi", "हिन्दी", "hi_IN"),
    Locale("ar", "ar", "العربية", "ar_AR", rtl=True),
    Locale("pt", "pt", "Português", "pt_BR"),
    Locale("fr", "fr", "Français", "fr_FR"),
    Locale("it", "it", "Italiano", "it_IT"),
    Locale("de", "de", "Deutsch", "de_DE"),
    Locale("ja", "ja", "日本語", "ja_JP"),
    Locale("ko", "ko", "한국어", "ko_KR"),
    Locale("id", "id", "Bahasa Indonesia", "id_ID"),
    Locale("tr", "tr", "Türkçe", "tr_TR"),
    Locale("vi", "vi", "Tiếng Việt", "vi_VN"),
    Locale("th", "th", "ไทย", "th_TH"),
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

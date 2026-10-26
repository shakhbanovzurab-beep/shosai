"""The name of the space a source belongs to, as the person reads it (ADR 0068 AG-D1).

A workspace's source shows the workspace's name; one of the person's own data shows their
Personal space, in the language of the answer — the words of the cabinet's space switcher, so
the panel and the switcher agree. A language the platform does not have reads in English. A
page of the web is of no space of the person's: it shows its site, without `www.`; a report of
the platform's, for the operator, shows the Platform.
"""

from collections.abc import Mapping
from typing import Final
from urllib.parse import urlsplit
from uuid import UUID

from shosai.core.agent_tools.sources import SourceKind, SourceRef

PERSONAL_SPACE: Final[Mapping[str, str]] = {
    "en": "Personal", "fr": "Personnel", "de": "Persönlich", "ru": "Личное",
    "nl": "Persoonlijk", "it": "Personale", "es": "Personal", "pt-BR": "Pessoal",
    "ar": "شخصي", "tr": "Kişisel", "ko": "개인", "hi": "निजी", "vi": "Cá nhân",
    "zh-Hant": "個人", "ja": "個人", "id": "Pribadi",
}  # fmt: skip
# Отчёты платформы оператору (AG-D5) — ни в чьём пространстве: «Платформа».
PLATFORM_SPACE: Final[Mapping[str, str]] = {
    "en": "Platform", "fr": "Plateforme", "de": "Plattform", "ru": "Платформа",
    "nl": "Platform", "it": "Piattaforma", "es": "Plataforma", "pt-BR": "Plataforma",
    "ar": "المنصة", "tr": "Platform", "ko": "플랫폼", "hi": "प्लेटफ़ॉर्म", "vi": "Nền tảng",
    "zh-Hant": "平台", "ja": "プラットフォーム", "id": "Platform",
}  # fmt: skip
FALLBACK_LANGUAGE: Final = "en"
# Сайт читается без «www.»: python.org, а не www.python.org.
WEB_PREFIX: Final = "www."


def personal_space(language: str) -> str:
    """The Personal space's name in the language, English for one the platform lacks."""
    return PERSONAL_SPACE.get(language, PERSONAL_SPACE[FALLBACK_LANGUAGE])


def space_of(ref: SourceRef, language: str, workspaces: Mapping[UUID, str]) -> str:
    """The space a source is listed with: its site, its workspace's name, or Personal."""
    if ref.kind is SourceKind.REPORT:
        return PLATFORM_SPACE.get(language, PLATFORM_SPACE[FALLBACK_LANGUAGE])
    if ref.kind is SourceKind.WEB:
        site = urlsplit(ref.id).hostname or ref.id
        return site.removeprefix(WEB_PREFIX)
    if ref.org_id is None:
        return personal_space(language)
    return workspaces[ref.org_id]

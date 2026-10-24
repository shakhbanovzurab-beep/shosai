"""The name of the space a source belongs to, as the person reads it (ADR 0068 AG-D1).

A workspace's source shows the workspace's name; one of the person's own data shows their
Personal space, in the language of the answer — the words of the cabinet's space switcher, so
the panel and the switcher agree. A language the platform does not have reads in English.
"""

from collections.abc import Mapping
from typing import Final

PERSONAL_SPACE: Final[Mapping[str, str]] = {
    "en": "Personal", "fr": "Personnel", "de": "Persönlich", "ru": "Личное",
    "nl": "Persoonlijk", "it": "Personale", "es": "Personal", "pt-BR": "Pessoal",
    "ar": "شخصي", "tr": "Kişisel", "ko": "개인", "hi": "निजी", "vi": "Cá nhân",
    "zh-Hant": "個人", "ja": "個人", "id": "Pribadi",
}  # fmt: skip
FALLBACK_LANGUAGE: Final = "en"


def personal_space(language: str) -> str:
    """The Personal space's name in the language, English for one the platform lacks."""
    return PERSONAL_SPACE.get(language, PERSONAL_SPACE[FALLBACK_LANGUAGE])

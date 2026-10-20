"""The words the native answers carry, in the 16 platform languages (user-facing, not a prompt).

The shipped clients show a speaker's label and the headings of Leo's write-up as the server
sends them, so the server words them in the person's language: "Speaker N" for a voice
without a name, a shipped template's headings and the four sections of Leo's layout.
`native_words.json` holds the cabinet's own translations (`notesShare.page.speaker`,
`notesTemplates.sections` and `.headings`); a test keeps it equal to them. It is read once,
when the slice is built.
"""

import json
from dataclasses import dataclass
from importlib.resources import files  # nosemgrep
from typing import Final

from shosai.core.i18n.locales import normalize_language

DEFAULT_LANGUAGE: Final = "en"


@dataclass(frozen=True, slots=True)
class LanguageWords:
    """One language's words."""

    speaker: str
    sections: dict[str, str]
    headings: dict[str, str]


@dataclass(frozen=True, slots=True)
class NativeWords:
    """The words of every platform language."""

    by_language: dict[str, LanguageWords]

    def of(self, language: str | None) -> LanguageWords:
        """The person's language's words, English for one outside the platform's."""
        return self.by_language[normalize_language(language) or DEFAULT_LANGUAGE]

    def speaker(self, language: str | None, number: int) -> str:
        """`Speaker N` in the language, N counted from one."""
        return self.of(language).speaker.replace("{n}", str(number))

    def heading(self, language: str | None, code: str) -> str:
        """A section's heading by its code: a shipped template's, or a section kind's."""
        words = self.of(language)
        return words.headings.get(code) or words.sections.get(code) or code


def load_native_words() -> NativeWords:
    """The words from the package."""
    raw = json.loads(files(__package__).joinpath("native_words.json").read_text("utf-8"))
    return NativeWords(
        {
            language: LanguageWords(
                str(words["speaker"]), dict(words["sections"]), dict(words["headings"])
            )
            for language, words in raw.items()
        }
    )

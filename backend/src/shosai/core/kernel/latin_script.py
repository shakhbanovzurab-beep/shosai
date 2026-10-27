"""Whether text a model reads is written in Latin script (CLAUDE.md "Prompts").

A letter outside the Latin script (Cyrillic, Greek, CJK) marks a non-English instruction:
a model takes the language of an instruction as a cue for the language of its answer.
Digits, punctuation, symbols and Latin letters with diacritics pass. The model-facing test
checks the code's texts by this rule, and studio checks the operator's platform text by it
before publishing.
"""

import unicodedata
from typing import Final

LATIN_LETTER_PREFIX: Final = "LATIN "


def non_latin_letters(text: str) -> list[str]:
    """Letters outside the Latin script, without repeats, in code point order."""
    return sorted(
        {
            char
            for char in text
            if char.isalpha() and not unicodedata.name(char, "").startswith(LATIN_LETTER_PREFIX)
        }
    )

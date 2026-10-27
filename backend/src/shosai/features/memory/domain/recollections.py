"""What a meeting may tell memory about its owner (memory step 9, ADR 0071 MM-D5).

The recollection reads the meeting's summary, its key points and who took part — never the
transcript — within about 1 500 tokens. A statement about the owner stands only when the
evidence it cites names the owner: what another participant said of themselves is never the
owner's. A statement about someone else, or a goal, stands on its evidence alone. Every
recollection waits for the person as a candidate.
"""

import unicodedata
from typing import Final

SUMMARY_EVIDENCE: Final = "summary"
SUMMARY_MAX: Final = 3_000
KEY_POINTS_MAX: Final = 20
KEY_POINT_MAX: Final = 300
QUOTE_MAX: Final = 200
# Часть имени короче двух знаков совпала бы с любым текстом.
NAME_PART_MIN: Final = 2


def _folded(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def names_owner(owner_name: str, evidence: str) -> bool:
    """Whether the evidence names the owner by any part of their name, in any script."""
    folded = _folded(evidence)
    parts = [part for part in _folded(owner_name).split() if len(part) >= NAME_PART_MIN]
    return any(part in folded for part in parts)


def clipped(text: str, limit: int) -> str:
    """The text cut to the limit on a word, so the model reads no half word."""
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    cut = cleaned[:limit].rsplit(" ", 1)[0]
    return f"{cut}…"

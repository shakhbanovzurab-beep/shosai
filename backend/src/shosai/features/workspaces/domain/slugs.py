"""A workspace's slug: its part of `/app/w/{slug}` (the cabinet's `domain/paths.ts`).

The slug is made once from the name and never changes, so links people shared keep
working after a rename. Letters and digits of every script are kept — a name in Russian
or Japanese gives a readable slug, the same rule for all 16 languages — and everything
else becomes a hyphen. "new" is the creation page and never a slug.
"""

import unicodedata
from collections.abc import Iterator
from typing import Final

SLUG_MAX_LENGTH: Final = 40
FALLBACK_SLUG: Final = "workspace"
RESERVED_SLUGS: Final = frozenset({"new"})


def base_slug(name: str) -> str:
    """The slug a name gives before any collision."""
    folded = unicodedata.normalize("NFKC", name).casefold()
    words: list[str] = []
    current: list[str] = []
    for char in folded:
        if char.isalnum():
            current.append(char)
        elif current:
            words.append("".join(current))
            current = []
    if current:
        words.append("".join(current))
    slug = "-".join(words)[:SLUG_MAX_LENGTH].strip("-")
    return slug if slug and slug not in RESERVED_SLUGS else FALLBACK_SLUG


def slug_candidates(name: str) -> Iterator[str]:
    """The base slug, then `base-2`, `base-3`, …; the first one free in the home is taken."""
    base = base_slug(name)
    yield base
    number = 2
    while True:
        suffix = f"-{number}"
        yield f"{base[: SLUG_MAX_LENGTH - len(suffix)].rstrip('-')}{suffix}"
        number += 1

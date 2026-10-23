"""A person's rating of an answer, and when a rated turn may help improve Leo (ADR 0068 AG-D13).

"Useful" or "Not useful" under an answer: one press, and pressing it again takes it back. The
rating alone is the person's and counts only in anonymous totals. A rated turn becomes an
evaluation case only with the person's `improve_models` consent at the time of rating, and
only when nothing it read belongs to a workspace — a person cannot consent for a company.
The case masks the person's name and leaves attachments' text out; it is kept a year at
most, and goes earlier with its rating, the consent, the thread or the account.
"""

import re
from collections.abc import Collection
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final
from uuid import UUID

CASE_RETENTION: Final = timedelta(days=365)
NAME_MASK: Final = "[name]"
# Имя короче — не маскируется: одна буква совпала бы с половиной текста.
NAME_MIN: Final = 2


class Rating(StrEnum):
    """What the person said about an answer."""

    USEFUL = "useful"
    NOT_USEFUL = "not_useful"


def case_allowed(source_spaces: Collection[UUID | None], *, consent_given: bool) -> bool:
    """Whether a rated turn may be kept as an evaluation case.

    `source_spaces` are the workspaces of the turn's sources, None for the person's own.
    """
    return consent_given and all(space is None for space in source_spaces)


def mask_names(text: str, names: Collection[str]) -> str:
    """The text with each of the person's names replaced, whatever their case.

    The names are matched as written — no rule depends on the text's language.
    """
    usable = sorted({name.strip() for name in names if len(name.strip()) >= NAME_MIN}, key=len)
    for name in reversed(usable):
        text = re.sub(re.escape(name), NAME_MASK, text, flags=re.IGNORECASE)
    return text


def case_expired(created_at: datetime, now: datetime) -> bool:
    """Whether a case passed its year."""
    return now - created_at >= CASE_RETENTION

"""The parts of a turn's context that rules decide (Leo §7.3, ADR 0031; agent plan step 5b).

The profile core — who Leo talks with, their time zone, the answer's language and length —
changes only when the person's settings do, so it stays byte-identical from turn to turn and
a provider keeps it cached with the policy before it. Time to the minute and the page the
person is on change every turn, so they come last, with the question. A cabinet path is the
person's page, never free text: anything outside a path's alphabet is dropped. Every segment
is cut to its cap; a cut keeps the beginning, which says what the text is.
"""

import re
import unicodedata
from datetime import datetime
from typing import Final

from shosai.features.agent.domain.budgets import BYTES_PER_TOKEN

NAME_MAX: Final = 80
PATH_MAX: Final = 200
CABINET_PATH: Final = re.compile(r"/[A-Za-z0-9/_\-.~%]{0,199}")
CUT: Final = " …"
# Строки контекста, которые читает модель: английские, зарегистрированы в тесте model-facing.
WITH: Final = "You are talking with {name}."
WITH_NOBODY: Final = "You are talking with the person."
ZONE: Final = "Their time zone is {zone}."
NOW: Final = "Now: {moment} ({zone})."
PAGE: Final = "The person is on the page {path} of Shosai."
CONTEXT_TEXTS: Final = (WITH, WITH_NOBODY, ZONE, NOW, PAGE)


def clean_name(name: str) -> str:
    """A display name as one line of printable characters, at most 80."""
    printable = "".join(char for char in name if not unicodedata.category(char).startswith("C"))
    return " ".join(printable.split())[:NAME_MAX]


def clean_path(path: str | None) -> str | None:
    """The cabinet path the person is on, or None for anything that is not one."""
    if path is None:
        return None
    bare = path.split("?", 1)[0].split("#", 1)[0]
    return bare if CABINET_PATH.fullmatch(bare) else None


def clip(text: str, tokens: int) -> str:
    """The text cut to a token budget at a character boundary, marked when cut."""
    limit = tokens * BYTES_PER_TOKEN
    encoded = text.encode()
    if len(encoded) <= limit:
        return text
    marker = len(CUT.encode())
    if limit <= marker:
        return encoded[:limit].decode(errors="ignore")
    return encoded[: limit - marker].decode(errors="ignore").rstrip() + CUT


def profile_core(name: str, zone: str | None, instructions: str) -> str:
    """Segment 4: the person, their time zone, the answer's language and length."""
    who = clean_name(name)
    lines = [WITH.format(name=who) if who else WITH_NOBODY]
    if zone:
        lines.append(ZONE.format(zone=zone))
    lines.append(instructions)
    return "\n".join(lines)


def now_line(moment: datetime, zone: str) -> str:
    """The person's local time to the minute, with the weekday and the zone."""
    return NOW.format(moment=moment.strftime("%A, %d %B %Y, %H:%M"), zone=zone)


def page_line(path: str) -> str:
    """The cabinet page the person is on."""
    return PAGE.format(path=path)

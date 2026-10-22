"""Card order inside a column by fractional keys (tasks plan §3.5 flow 3).

The draft kept dense positions and rewrote every card of two columns on a move, so moves
and inserts raced (draft lesson, `me_tracker.py:288`). Here a card's place is a key: a
move or an insert writes one key, strictly between its new neighbours. Keys are base-62
digits in ASCII order, so the database orders them with `COLLATE "C"` exactly as Python
compares them, and never end with the lowest digit, so a key always fits between two.
A column whose keys grow past 48 characters is given evenly spaced keys again.
"""

from collections.abc import Sequence
from typing import Final

DIGITS: Final = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
ZERO: Final = DIGITS[0]
REBALANCE_LENGTH: Final = 48


class RankError(ValueError):
    """Keys out of order or malformed: a programming error, never a person's."""


def _check(key: str) -> None:
    if not key or key.endswith(ZERO) or any(char not in DIGITS for char in key):
        message = f"ключ порядка {key!r} — непустые цифры base-62 без нуля в конце"
        raise RankError(message)


def _midpoint(low: str, high: str | None) -> str:
    """A key strictly between `low` (empty: the bottom) and `high` (None: the top)."""
    if high is not None:
        common = 0
        while common < len(high) and (low[common] if common < len(low) else ZERO) == high[common]:
            common += 1
        if common:
            return high[:common] + _midpoint(low[common:], high[common:])
    digit_low = DIGITS.index(low[0]) if low else 0
    digit_high = DIGITS.index(high[0]) if high is not None else len(DIGITS)
    if digit_high - digit_low > 1:
        return DIGITS[(digit_low + digit_high) // 2]
    if high is not None and len(high) > 1:
        return high[:1]
    return DIGITS[digit_low] + _midpoint(low[1:], None)


def rank_between(before: str | None, after: str | None) -> str:
    """The key of a card placed after `before` and before `after` (None: the column's end)."""
    for key in (before, after):
        if key is not None:
            _check(key)
    if before is not None and after is not None and before >= after:
        message = f"ключи не по порядку: {before!r} ≥ {after!r}"
        raise RankError(message)
    return _midpoint(before or "", after)


def rank_at(ranks: Sequence[str], position: int) -> str:
    """The key for a card put at `position` among a column's other cards, 0 the top.

    A position past the end puts it last, a negative one first, as the cabinet's mocks do.
    """
    index = min(max(position, 0), len(ranks))
    before = ranks[index - 1] if index > 0 else None
    after = ranks[index] if index < len(ranks) else None
    return rank_between(before, after)


def needs_rebalance(key: str) -> bool:
    """Whether a column should get evenly spaced keys after writing this one."""
    return len(key) > REBALANCE_LENGTH


def spaced_ranks(count: int) -> tuple[str, ...]:
    """`count` keys spread evenly, in order, as short as possible."""
    if count < 0:
        message = "число ключей — от нуля"
        raise RankError(message)
    length = 1
    while len(DIGITS) ** length <= count:
        length += 1
    step = len(DIGITS) ** length // (count + 1)
    return tuple(_digits((index + 1) * step, length).rstrip(ZERO) for index in range(count))


def _digits(value: int, length: int) -> str:
    out = []
    for _ in range(length):
        value, digit = divmod(value, len(DIGITS))
        out.append(DIGITS[digit])
    return "".join(reversed(out))

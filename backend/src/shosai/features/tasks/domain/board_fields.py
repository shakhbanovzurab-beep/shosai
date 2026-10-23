"""What a board shows besides its cards: column colours and its system fields (§3.8, §3.14).

A column has one of nine colours, or none. Every board shows the seven system fields — the
task's own assignee, due day, priority, recurrence and its three time fields (ADR 0061) —
a new board the first three only; the stopwatch carries its automations, by default
restarted on a move and stopped when done. A Jira board has no time fields (KG-D8).
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class Color(StrEnum):
    """A colour of the palette the cabinet maps to Tailwind's, light and dark."""

    GRAY = "gray"
    RED = "red"
    ORANGE = "orange"
    AMBER = "amber"
    GREEN = "green"
    TEAL = "teal"
    BLUE = "blue"
    VIOLET = "violet"
    PINK = "pink"


class SystemSticker(StrEnum):
    """A field every board has: the task's own data, in the board's order."""

    ASSIGNEE = "assignee"
    DUE = "due"
    PRIORITY = "priority"
    RECURRENCE = "recurrence"
    STOPWATCH = "stopwatch"
    TIMER = "timer"
    TIME_TRACKING = "time_tracking"


TIME_STICKERS: Final = frozenset(
    {SystemSticker.STOPWATCH, SystemSticker.TIMER, SystemSticker.TIME_TRACKING}
)
NEW_BOARD_VISIBILITY: Final = {
    sticker: sticker in {SystemSticker.ASSIGNEE, SystemSticker.DUE, SystemSticker.PRIORITY}
    for sticker in SystemSticker
}


@dataclass(frozen=True, slots=True)
class StopwatchAutomations:
    """What the stopwatch does by itself on a board (KT-D2)."""

    start_on_arrival: bool = False
    restart_on_move: bool = True
    stop_on_done: bool = True


DEFAULT_AUTOMATIONS: Final = StopwatchAutomations()

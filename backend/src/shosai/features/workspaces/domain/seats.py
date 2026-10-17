"""Seats: how many people a workspace holds and when it is full (inv-16; the cabinet's rule).

A seat is held by every standing member (active or hidden) and by every pending
invitation, so an invitation never promises a place that a join would then refuse.
Billing sells the seats; this slice only counts them (ADR 0053 point 7).
"""

from dataclasses import dataclass
from typing import Final

SEATS_AT_CREATION_MIN: Final = 2
SEATS_AT_CREATION_MAX: Final = 100
# Потолок, который ставит администратор платформы (экран admin workspaces).
SEATS_MAX: Final = 500


@dataclass(frozen=True, slots=True)
class SeatUse:
    """The seats a workspace pays for and the ones taken."""

    paid: int
    members: int
    pending_invitations: int

    @property
    def taken(self) -> int:
        """Members plus pending invitations."""
        return self.members + self.pending_invitations

    @property
    def left(self) -> int:
        """Seats still free; never below zero."""
        return max(self.paid - self.taken, 0)

    def admits(self, newcomers: int) -> bool:
        """Whether this many more invitations or joins fit; an invited join adds none."""
        return self.taken + newcomers <= self.paid


def seats_at_creation_valid(seats: int) -> bool:
    """Whether a new workspace may start with this many seats."""
    return SEATS_AT_CREATION_MIN <= seats <= SEATS_AT_CREATION_MAX


def seats_change_valid(seats: int, use: SeatUse) -> bool:
    """Whether the platform may set this many seats: never below what is taken, at most 500."""
    return use.taken <= seats <= SEATS_MAX

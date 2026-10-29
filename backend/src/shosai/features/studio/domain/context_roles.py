"""Where a person's own words go (ADR 0074 ST-D2, amended by the owner on 2026-10-29).

The person chooses the Studio roles whose answers take their "About you": every role — the
default, which also takes any role added later — or the roles they name, which may be none.
Leo always takes it. Notes are a role like the others: colleagues read them, which the cabinet
says next to their switch.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final, Literal

from shosai.features.studio.domain.roles import PromptRole

EVERY_ROLE: Final = "all"

type ContextRolesWire = Literal["all"] | list[PromptRole]


@dataclass(frozen=True, slots=True)
class ContextRoles:
    """Every Studio role, or the ones named; never both."""

    every: bool = True
    named: frozenset[PromptRole] = frozenset()

    def __post_init__(self) -> None:
        if self.every and self.named:
            message = "«все роли» не называет ролей"
            raise ValueError(message)

    @classmethod
    def of(cls, wire: ContextRolesWire) -> ContextRoles:
        """The choice as the API carries it: "all", or the roles, repeats ignored."""
        if isinstance(wire, str):
            return cls()
        return cls.only(wire)

    @classmethod
    def only(cls, roles: Iterable[PromptRole]) -> ContextRoles:
        """The roles named, and no other."""
        return cls(every=False, named=frozenset(roles))

    def reaches(self, role: PromptRole | None) -> bool:
        """Whether an answer in the role takes the words; None is Leo, which always does."""
        return role is None or self.every or role in self.named

    def wire_named(self) -> list[PromptRole]:
        """The roles named, in the roles' order; none while every role takes the words."""
        return [role for role in PromptRole if role in self.named]

    def wire(self) -> ContextRolesWire:
        """The choice for the API: "all", or the roles in the roles' order."""
        return EVERY_ROLE if self.every else self.wire_named()

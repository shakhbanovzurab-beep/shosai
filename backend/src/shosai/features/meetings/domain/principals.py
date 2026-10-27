"""Who is in a call: a principal, and the identity of each of its sessions (meetings plan §1.2).

A principal is a person's user id or, for someone who joined by link without signing in,
`guest-` and 12 hex digits. Each join gets its own LiveKit identity, the principal and 8 hex
digits after `__`, so one person on two devices keeps both sessions (the draft's
`DUPLICATE_IDENTITY` lesson). Rights and bans are keyed by the principal, never by the
identity, so a change reaches every session of that principal.
"""

import re
import secrets
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from typing import Final
from uuid import UUID

GUEST_PREFIX: Final = "guest-"
GUEST_HEX: Final = 6
SESSION_HEX: Final = 4
IDENTITY_SEPARATOR: Final = "__"
NAME_MAX: Final = 100
GUEST: Final = re.compile(r"guest-[0-9a-f]{12}")
SESSION: Final = re.compile(r"[0-9a-f]{8}")
PRINCIPAL_MAX: Final = 64
# Встраивания, переопределения и изоляции направления текста (U+202A…U+202E, U+2066…U+2069).
BIDI_CONTROLS: Final = frozenset(map(chr, (*range(0x202A, 0x202F), *range(0x2066, 0x206A))))


class PrincipalKind(StrEnum):
    """Whether a principal signed in."""

    USER = "user"
    GUEST = "guest"


class NameRule(StrEnum):
    """A rule of a display name; the value is the API's error code."""

    NAME_REQUIRED = "name_required"
    NAME_TOO_LONG = "name_too_long"


class NameRuleError(ValueError):
    """A display name breaks a rule."""

    def __init__(self, rule: NameRule) -> None:
        super().__init__(rule.value)
        self.rule = rule
        self.code = rule.value


@dataclass(frozen=True, slots=True, order=True)
class Principal:
    """A person in a call, signed in or a guest; its text form is the key of rights and bans."""

    value: str

    def __post_init__(self) -> None:
        if not (GUEST.fullmatch(self.value) or _is_user_id(self.value)):
            message = "принципал — id пользователя или guest-<12 hex>"
            raise ValueError(message)

    @classmethod
    def of_user(cls, user_id: UUID) -> Principal:
        """The principal of a signed-in person."""
        return cls(str(user_id))

    @classmethod
    def new_guest(cls) -> Principal:
        """A fresh guest principal; a guest who joins again is a new principal."""
        return cls(f"{GUEST_PREFIX}{secrets.token_hex(GUEST_HEX)}")

    @property
    def kind(self) -> PrincipalKind:
        """Whether this principal signed in."""
        return PrincipalKind.GUEST if self.value.startswith(GUEST_PREFIX) else PrincipalKind.USER

    @property
    def user_id(self) -> UUID | None:
        """The person's id; None for a guest."""
        return None if self.kind is PrincipalKind.GUEST else UUID(self.value)


def new_identity(principal: Principal) -> str:
    """A LiveKit identity for one session of the principal."""
    return f"{principal.value}{IDENTITY_SEPARATOR}{secrets.token_hex(SESSION_HEX)}"


def principal_of(identity: str) -> Principal | None:
    """The principal of a session's identity; None for one Shosai did not mint (egress, agents)."""
    value, separator, session = identity.rpartition(IDENTITY_SEPARATOR)
    if not separator or not SESSION.fullmatch(session):
        return None
    try:
        return Principal(value)
    except ValueError:
        return None


def checked_name(raw: str | None) -> str:
    """A display name: trimmed, control characters dropped, 1 to 100 characters.

    A participant may rename themselves in the call, as a guest may choose any name at the
    door; the chat's author is the name the pass was issued with (MR-D11).
    """
    if raw is None:
        raise NameRuleError(NameRule.NAME_REQUIRED)
    # Управляющие символы и переключатели направления текста не попадают в имя: ими подделывают
    # чужое имя. ZWJ и ZWNJ остаются — без них ломаются эмодзи, хинди и фарси.
    name = "".join(
        ch for ch in raw if unicodedata.category(ch) != "Cc" and ch not in BIDI_CONTROLS
    ).strip()
    if not name:
        raise NameRuleError(NameRule.NAME_REQUIRED)
    if len(name) > NAME_MAX:
        raise NameRuleError(NameRule.NAME_TOO_LONG)
    return name


def _is_user_id(value: str) -> bool:
    if len(value) > PRINCIPAL_MAX:
        return False
    try:
        parsed = UUID(value)
    except ValueError:
        return False
    # Только каноническая запись: иначе один человек получил бы два принципала.
    return str(parsed) == value

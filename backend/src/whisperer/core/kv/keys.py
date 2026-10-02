"""Key layout of the Redis-protocol servers: `whisperer:<purpose>:<part>…`.

Parts are ids and codes from a closed alphabet without `:`, so a key's structure is
unambiguous, no glob character reaches `SCAN` patterns and no free text — a name, an
email — can become a key.
"""

import re
from typing import Final

KEY_PREFIX: Final = "whisperer"
KEY_PART: Final = re.compile(r"[A-Za-z0-9_.-]{1,128}")


def build_key(*parts: str) -> str:
    """`build_key("lock", "relay.ru")` → `whisperer:lock:relay.ru`."""
    for part in parts:
        check_key_part(part)
    return ":".join((KEY_PREFIX, *parts))


def check_key_part(part: str) -> str:
    """Reject a part outside the alphabet; the message never repeats the part itself."""
    if not KEY_PART.fullmatch(part):
        message = "часть ключа — латиница, цифры, «_», «.», «-», от 1 до 128 символов"
        raise ValueError(message)
    return part

"""Object keys of the one bucket: refused when they could escape their prefix or break a URL.

Keys are prefixed by their owner (§8.1); S08 decides the layout and the draft's keys are
kept as they are (ADR 0006), so the check refuses only what is dangerous anywhere: an
empty or overlong key, a leading `/`, an empty, `.` or `..` segment, a backslash and
control characters. A key may contain a file name, so it never enters logs or spans.
"""

import re
from typing import Final

MAX_KEY_BYTES: Final = 1024
CONTROL_CHARACTERS: Final = re.compile(r"[\x00-\x1f\x7f]")
FORBIDDEN_SEGMENTS: Final = frozenset({"", ".", ".."})


def check_object_key(key: str) -> str:
    """The key itself when it is safe; otherwise `ValueError` without the key in the message."""
    if not key or len(key.encode()) > MAX_KEY_BYTES:
        message = f"ключ объекта — от 1 до {MAX_KEY_BYTES} байт в UTF-8"
        raise ValueError(message)
    if "\\" in key or CONTROL_CHARACTERS.search(key):
        message = "ключ объекта — без обратной косой черты и управляющих символов"
        raise ValueError(message)
    if FORBIDDEN_SEGMENTS.intersection(key.split("/")):
        message = "ключ объекта не начинается с «/», в нём нет пустых сегментов, «.» и «..»"
        raise ValueError(message)
    return key


def check_prefix(prefix: str) -> str:
    """A listing prefix: empty, or a safe key with or without a trailing `/`."""
    if prefix:
        check_object_key(prefix.removesuffix("/"))
    return prefix


def check_root(root: str) -> str:
    """The root prefix an adapter works under: empty, or a safe prefix ending with `/`."""
    if root and not root.endswith("/"):
        message = "корневой префикс хранилища пуст или оканчивается на «/»"
        raise ValueError(message)
    return check_prefix(root)

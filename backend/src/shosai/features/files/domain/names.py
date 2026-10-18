"""A file's or a folder's name, as the cabinet allows it (`file-manager/domain/contract.ts`).

A name is trimmed and holds 1 to 120 characters, with no slash, backslash or control
character. Two files may share a name. Each broken rule carries the API's error code.
"""

import unicodedata
from enum import StrEnum
from typing import Final

NAME_MAX: Final = 120


class NameRule(StrEnum):
    """A rule of names; the value is the API's error code."""

    REQUIRED = "name_required"
    TOO_LONG = "name_too_long"
    SLASH = "name_slash"
    CONTROL = "name_control_character"


class NameRuleError(ValueError):
    """A name breaks a rule."""

    def __init__(self, rule: NameRule) -> None:
        super().__init__(rule.value)
        self.rule = rule
        self.code = rule.value


def checked_name(raw: str) -> str:
    """The trimmed name, or the rule it breaks."""
    name = raw.strip()
    if not name:
        raise NameRuleError(NameRule.REQUIRED)
    if len(name) > NAME_MAX:
        raise NameRuleError(NameRule.TOO_LONG)
    if "/" in name or "\\" in name:
        raise NameRuleError(NameRule.SLASH)
    if any(unicodedata.category(char) == "Cc" for char in name):
        raise NameRuleError(NameRule.CONTROL)
    return name


def copy_name(name: str, taken: set[str]) -> str:
    """`Report (2).pdf` for `Report.pdf`: the first number no other file of the place has."""
    dot = name.rfind(".")
    base, extension = (name[:dot], name[dot:]) if dot > 0 else (name, "")
    if len(extension) > NAME_MAX // 2:
        base, extension = name, ""
    number = 2
    while True:
        suffix = f" ({number}){extension}"
        candidate = base[: NAME_MAX - len(suffix)] + suffix
        if candidate not in taken:
            return candidate
        number += 1

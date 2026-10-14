"""Profile rules: names, work roles, time zones and which consents a person may change.

Personal-data consent is not a switch: withdrawing it is deleting the account. Withdrawing
cross-border consent stops every AI function for a Russian-home person, meeting
transcription included, so it takes effect only after the cabinet showed exactly that
and the person confirmed it (ID-D2).
"""

from enum import StrEnum
from typing import Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from shosai.features.identity.domain.registration import ConsentKind

NAME_LENGTH: Final = 80
# Роли из настроек кабинета (Settings › Account): по ним Leo подбирает тон ответов.
WORK_ROLES: Final = frozenset(
    {
        "product_management", "engineering", "human_resources", "finance", "marketing",
        "sales", "operations", "data_science", "design", "legal", "scientist", "student",
        "founder", "healthcare", "writer", "educator", "consultant", "researcher",
        "software_engineer", "other",
    }
)  # fmt: skip
SWITCHABLE: Final = frozenset(
    {
        ConsentKind.CROSS_BORDER,
        ConsentKind.MARKETING,
        ConsentKind.IMPROVE_MODELS,
        ConsentKind.SHARE_LOCATION,
    }
)


class ProfileProblem(StrEnum):
    """Why a profile change is refused; the value is the client's error code."""

    UNKNOWN_WORK_ROLE = "unknown_work_role"
    UNKNOWN_TIMEZONE = "unknown_timezone"
    BLANK_NAME = "blank_name"
    CONSENT_WARNING_REQUIRED = "consent_warning_required"


def valid_timezone(name: str) -> bool:
    """Whether the name is an IANA time zone."""
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError, ValueError:
        return False
    return True


def clean_name(name: str) -> str | None:
    """The name without surrounding spaces, or None when nothing is left."""
    cleaned = " ".join(name.split())
    return cleaned[:NAME_LENGTH] if cleaned else None


def withdrawal_needs_warning(kind: ConsentKind, *, current: bool, wanted: bool) -> bool:
    """Whether this change is the cross-border withdrawal that needs a confirmed warning."""
    return kind is ConsentKind.CROSS_BORDER and current and not wanted

"""How much of an application's quota a provider says is used, from the IETF RateLimit headers.

Atlassian's points quota (65 000 an hour for an app across all its customers) comes as a
`RateLimit-Policy` header naming the quota `q` and its window `w` in seconds and, once 80% is
used, a `RateLimit` header naming the remainder `r` — both with a `Beta-` prefix during
Atlassian's beta. The session counts each answer past 80%, and the alert reads that counter
(plan §3.11).
"""

from collections.abc import Mapping
from typing import Final

NEAR_QUOTA: Final = 0.8
POLICY_HEADERS: Final = ("ratelimit-policy", "beta-ratelimit-policy")
LIMIT_HEADERS: Final = ("ratelimit", "beta-ratelimit")


def _parameter(header: str | None, name: str) -> int | None:
    """The integer parameter `name` of a structured header's first item, or None."""
    if not header:
        return None
    for part in header.split(",")[0].split(";")[1:]:
        key, _, value = part.strip().partition("=")
        if key == name and value.isdigit():
            return int(value)
    return None


def _first(headers: Mapping[str, str], names: tuple[str, ...]) -> str | None:
    lowered = {key.lower(): value for key, value in headers.items()}
    return next((lowered[name] for name in names if name in lowered), None)


def quota_used(headers: Mapping[str, str]) -> float | None:
    """The used share of the quota, when the provider named both the quota and its remainder."""
    quota = _parameter(_first(headers, POLICY_HEADERS), "q")
    remaining = _parameter(_first(headers, LIMIT_HEADERS), "r")
    if quota is None or remaining is None or quota <= 0:
        return None
    return max(0.0, min(1.0, 1 - remaining / quota))


def near_quota(headers: Mapping[str, str]) -> bool:
    """Whether the answer says at least 80% of the application's quota is used."""
    used = quota_used(headers)
    return used is not None and used >= NEAR_QUOTA

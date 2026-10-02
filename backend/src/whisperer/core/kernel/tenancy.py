"""Tenancy scope of one unit of work: whose data it touches and in which home (§4.1, §7)."""

from dataclasses import dataclass
from uuid import UUID

from whisperer.core.kernel.homes import Home


@dataclass(frozen=True, slots=True)
class TenancyScope:
    """The home a transaction opens in and the account and company it acts for.

    A request builds it from the access token (the token carries the home); a task builds
    it from its payload. Without `user_id` and `org_id` the scope is the platform's own
    work in that home, and row-level security shows it no company's rows.
    """

    home: Home
    user_id: UUID | None = None
    org_id: UUID | None = None

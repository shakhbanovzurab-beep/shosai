"""What a subscription entitles to at a moment, judged by time alone (draft lesson; ADR 0054).

A stored status is never trusted: a plan is in force until its expiry, and past it for
the renewal grace only while auto-renewal is on — a renewal is being attempted. A trial
ends without grace (BL-D5). Past that, the person has the Free plan: a lapsed paid plan
never keeps its limits (the draft kept unlimited minutes for lapsed plans).
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from shosai.features.billing.domain.plans import Plan

# Льгота после неудачного автопродления оплаченной подписки (BL-D5).
RENEWAL_GRACE: Final = timedelta(days=7)
DAY: Final = timedelta(days=1)


@dataclass(frozen=True, slots=True)
class SubscriptionFacts:
    """A subscription as the entitlement rules read it."""

    plan: Plan
    # None — без срока: тариф действует, пока его не сменят.
    expires_at: datetime | None
    auto_renew: bool
    trial: bool = False


@dataclass(frozen=True, slots=True)
class Entitled:
    """The plan in force at a moment, and whether it is a paid one still running."""

    plan: Plan
    paid: bool
    in_grace: bool
    paid_until: datetime | None


def access_deadline(facts: SubscriptionFacts) -> datetime | None:
    """When access ends: the expiry, plus the grace while auto-renewal is on and not a trial."""
    if facts.expires_at is None:
        return None
    if facts.auto_renew and not facts.trial:
        return facts.expires_at + RENEWAL_GRACE
    return facts.expires_at


def entitled(facts: SubscriptionFacts | None, free: Plan, now: datetime) -> Entitled:
    """The plan a person or a workspace may use now."""
    if facts is None:
        return Entitled(free, paid=False, in_grace=False, paid_until=None)
    deadline = access_deadline(facts)
    if deadline is not None and now >= deadline:
        return Entitled(free, paid=False, in_grace=False, paid_until=None)
    in_grace = facts.expires_at is not None and now >= facts.expires_at
    return Entitled(
        facts.plan,
        paid=not facts.plan.free,
        in_grace=in_grace,
        paid_until=facts.expires_at,
    )


def days_left(expires_at: datetime | None, now: datetime) -> int | None:
    """Whole days until expiry, rounded up, as the native clients show them; None without one."""
    if expires_at is None:
        return None
    return max(math.ceil((expires_at - now) / DAY), 0)

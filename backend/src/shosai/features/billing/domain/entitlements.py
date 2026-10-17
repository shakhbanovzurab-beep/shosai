"""What a subscription entitles to at a moment, judged by time alone (draft lesson; ADR 0054).

A stored status is never trusted: a plan is in force until its expiry, and past it for
the renewal grace only while auto-renewal is on — a renewal is being attempted. A trial
ends without grace (BL-D5). Plans waiting in the queue (the draft's frozen segments) run
one after another from the expiry, each for its days, and leave no gap for a grace. Past
all of it, the person has the Free plan: a lapsed paid plan never keeps its limits (the
draft kept unlimited minutes for lapsed plans).
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
class QueuedPlan:
    """A plan waiting for the one in force to end, with the days it still has."""

    plan: Plan
    days: int

    def __post_init__(self) -> None:
        if self.days < 1:
            message = "у тарифа в очереди есть хотя бы один день"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class SubscriptionFacts:
    """A subscription as the entitlement rules read it."""

    plan: Plan
    # None — без срока: тариф действует, пока его не сменят.
    expires_at: datetime | None
    auto_renew: bool
    trial: bool = False
    queued: tuple[QueuedPlan, ...] = ()


@dataclass(frozen=True, slots=True)
class Entitled:
    """The plan in force at a moment, and whether it is a paid one still running."""

    plan: Plan
    paid: bool
    in_grace: bool
    paid_until: datetime | None


def access_deadline(facts: SubscriptionFacts) -> datetime | None:
    """When the plan in force ends: its expiry, plus the grace while it is being renewed.

    The grace needs auto-renewal, a paid plan rather than a trial, and nothing queued.
    """
    if facts.expires_at is None:
        return None
    if facts.auto_renew and not facts.trial and not facts.queued:
        return facts.expires_at + RENEWAL_GRACE
    return facts.expires_at


def queue_windows(facts: SubscriptionFacts) -> list[tuple[QueuedPlan, datetime, datetime]]:
    """Each queued plan with the moments it starts and ends, from the expiry on."""
    if facts.expires_at is None:
        return []
    windows = []
    start = facts.expires_at
    for queued in facts.queued:
        end = start + queued.days * DAY
        windows.append((queued, start, end))
        start = end
    return windows


def entitled(facts: SubscriptionFacts | None, free: Plan, now: datetime) -> Entitled:
    """The plan a person or a workspace may use now."""
    lapsed = Entitled(free, paid=False, in_grace=False, paid_until=None)
    if facts is None:
        return lapsed
    expires_at = facts.expires_at
    if expires_at is None or now < expires_at:
        return Entitled(facts.plan, paid=not facts.plan.free, in_grace=False, paid_until=expires_at)
    for queued, start, end in queue_windows(facts):
        if start <= now < end:
            return Entitled(queued.plan, paid=not queued.plan.free, in_grace=False, paid_until=end)
    deadline = access_deadline(facts)
    if facts.queued or deadline is None or now >= deadline:
        return lapsed
    return Entitled(facts.plan, paid=not facts.plan.free, in_grace=True, paid_until=expires_at)


def next_change(facts: SubscriptionFacts | None, now: datetime) -> datetime | None:
    """The first moment after `now` when the plan in force may change; None if never by time."""
    if facts is None or facts.expires_at is None:
        return None
    moments = [facts.expires_at, *(end for _, _, end in queue_windows(facts))]
    deadline = access_deadline(facts)
    if deadline is not None:
        moments.append(deadline)
    return min((moment for moment in moments if moment > now), default=None)


def days_left(expires_at: datetime | None, now: datetime) -> int | None:
    """Whole days until expiry, rounded up, as the native clients show them; None without one."""
    if expires_at is None:
        return None
    return max(math.ceil((expires_at - now) / DAY), 0)

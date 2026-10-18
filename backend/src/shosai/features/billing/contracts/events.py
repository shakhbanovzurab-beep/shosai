"""The events billing publishes (billing plan §3.2): ids, amounts in minor units, codes, times.

Consumers: workspaces follows seats and suspension, alerting reports payments, refunds and
sales inquiries (ADR 0052), proactive may tell a person their minutes ran out.
"""

from datetime import datetime
from enum import StrEnum
from typing import ClassVar
from uuid import UUID

from shosai.core.events.domain_event import DomainEvent, EventCode
from shosai.features.billing.domain.money import Currency


class Meter(StrEnum):
    """A usage meter that ran out."""

    MEETING_MINUTES = "meeting_minutes"
    FRONTIER_TOKENS = "frontier_tokens"
    STANDARD_TOKENS = "standard_tokens"


class PaymentSucceeded(DomainEvent):
    """A payment was confirmed and its grant applied, in the same transaction."""

    event_type: ClassVar[str] = "billing.payment.succeeded"
    version: ClassVar[int] = 1
    transaction_id: UUID
    user_id: UUID | None = None
    org_id: UUID | None = None
    amount_minor: int
    currency: Currency
    product: EventCode


class PaymentRefunded(DomainEvent):
    """Part or all of a payment was returned; the days it paid for ended."""

    event_type: ClassVar[str] = "billing.payment.refunded"
    version: ClassVar[int] = 1
    transaction_id: UUID
    amount_minor: int
    currency: Currency


class SubscriptionChanged(DomainEvent):
    """A person's or a workspace's plan or its paid period changed."""

    event_type: ClassVar[str] = "billing.subscription.changed"
    version: ClassVar[int] = 1
    subscription_id: UUID
    user_id: UUID | None = None
    org_id: UUID | None = None
    plan_slug: EventCode
    paid_until: datetime | None = None


class SeatsChanged(DomainEvent):
    """A workspace's paid seats changed."""

    event_type: ClassVar[str] = "billing.seats.changed"
    version: ClassVar[int] = 1
    org_id: UUID
    seats: int


class QuotaExhausted(DomainEvent):
    """A person used up one of their meters for its period."""

    event_type: ClassVar[str] = "billing.quota.exhausted"
    version: ClassVar[int] = 1
    user_id: UUID
    meter: Meter


class SalesInquiryReceived(DomainEvent):
    """A person asked sales about a custom-priced plan; the details stay in their home."""

    event_type: ClassVar[str] = "billing.sales_inquiry.received"
    version: ClassVar[int] = 1
    inquiry_id: UUID
    user_id: UUID
    team_size: EventCode

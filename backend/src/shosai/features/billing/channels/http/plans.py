"""The person's plans and sales inquiries (`/v1/billing/plans`, `/v1/billing/sales-inquiry`).

In the cabinet's contract (`upgrade/domain/contract.ts`): a plan's `id` is its slug, its
price is the monthly one in the account's currency, per user on a team plan, and null
for a custom price. A seat in a workspace arrives with workspace subscriptions (step 12);
until then the effective plan is the person's own.
"""

from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Annotated, Final, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, StringConstraints

from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.core.web.rate_limit import rate_limited
from shosai.features.billing.application.people_views import PeopleViews
from shosai.features.billing.application.sales import SalesInquiries, SalesInquiry
from shosai.features.billing.domain.meters import SECONDS_IN_MINUTE
from shosai.features.billing.domain.money import Currency
from shosai.features.billing.domain.plans import Audience, BillingPeriod, Capability, Plan
from shosai.features.identity.contracts import Principal, bearer_principal

# Заявок в отдел продаж — не больше пяти в час с одного адреса.
INQUIRY_LIMIT: Final = RateLimit("billing.sales_inquiry", 5, timedelta(hours=1), 5)
CABINET_CAPABILITIES: Final = tuple(c for c in Capability if c is not Capability.FRONTIER_MODELS)


class SeatsView(BaseModel):
    """How many users a team plan is sold for."""

    min: int
    max: int | None


class PriceView(BaseModel):
    """A monthly price in minor units of the account's currency."""

    amount_cents: int
    currency: Currency
    interval: Literal["month"]


class EntitlementsView(BaseModel):
    """What a plan unlocks: null is unlimited, 0 is not included."""

    meeting_minutes_per_month: int | None
    file_manager_gb: int | None
    knowledge_base_mb: int | None
    shared_workspace: bool
    member_management: bool
    centralized_billing: bool
    sso: bool
    admin_controls: bool
    priority_support: bool
    usage_analytics: bool


class PlanCard(BaseModel):
    """A plan on the pricing page."""

    id: str
    name: str
    tagline: str
    audience: Audience
    seats: SeatsView | None
    price: PriceView | None
    entitlements: EntitlementsView
    features: list[str]
    highlighted: bool


class SeatView(BaseModel):
    """A workspace seat whose plan covers the member's own tools."""

    workspace_name: str
    plan_id: str


class MeetingUsageView(BaseModel):
    """The month's meeting minutes; `limit_minutes` is null on unlimited plans."""

    used_minutes: float
    limit_minutes: int | None
    resets_at: datetime


class PlansView(BaseModel):
    """The plans, the person's own and effective plan, and the month's minutes."""

    plans: list[PlanCard]
    current_plan_id: str
    seat: SeatView | None
    effective_plan_id: str
    usage: MeetingUsageView


class SalesInquiryBody(BaseModel):
    """An Enterprise request for sales."""

    model_config = ConfigDict(extra="forbid")

    work_email: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        ),
    ]
    company: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    team_size: Literal["1-10", "11-50", "51-200", "201-1000", "1000+"]
    message: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class SalesInquiryAnswer(BaseModel):
    """The inquiry was received."""

    status: Literal["received"]


def card_of(plan: Plan, currency: Currency) -> PlanCard:
    """The pricing card of a plan in the account's currency."""
    limits = plan.limits
    price = None if plan.custom_pricing else PriceView(
        amount_cents=plan.prices[BillingPeriod.MONTH].of(currency).minor,
        currency=currency, interval="month",
    )  # fmt: skip
    seats = None if plan.seats is None else SeatsView(min=plan.seats.min, max=plan.seats.max)
    return PlanCard(
        id=plan.slug, name=plan.name, tagline=plan.description, audience=plan.audience,
        seats=seats, price=price,
        entitlements=EntitlementsView(
            meeting_minutes_per_month=limits.meeting_minutes_per_month,
            file_manager_gb=limits.file_manager_gb, knowledge_base_mb=limits.knowledge_base_mb,
            **{c.value: c in plan.capabilities for c in CABINET_CAPABILITIES},
        ),
        features=list(plan.features), highlighted=plan.featured,
    )  # fmt: skip


def build_plans_router(
    views: PeopleViews, inquiries: SalesInquiries, ports: PortDirectory, limiter: RateLimiter
) -> APIRouter:
    """The person's plan routes."""
    router = APIRouter(prefix="/v1/billing", tags=["billing"])
    signed_in = bearer_principal(ports)

    @router.get("/plans")
    async def list_plans(principal: Annotated[Principal, Depends(signed_in)]) -> PlansView:
        """The plans on sale with the person's own, in their currency, and the month's minutes."""
        found = await views.plans(principal)
        minutes = found.minutes
        return PlansView(
            plans=[card_of(plan, found.currency) for plan in found.plans],
            current_plan_id=found.current.slug, seat=None, effective_plan_id=found.current.slug,
            usage=MeetingUsageView(
                used_minutes=round(minutes.used_seconds / SECONDS_IN_MINUTE, 1),
                limit_minutes=minutes.limit_minutes, resets_at=minutes.resets_at,
            ),
        )  # fmt: skip

    @router.post(
        "/sales-inquiry",
        status_code=HTTPStatus.ACCEPTED,
        dependencies=[Depends(rate_limited(limiter, INQUIRY_LIMIT))],
    )
    async def ask_sales(
        principal: Annotated[Principal, Depends(signed_in)], body: SalesInquiryBody
    ) -> SalesInquiryAnswer:
        """Store the request; the owner is told with its ids and team size only."""
        inquiry = SalesInquiry(body.work_email, body.company, body.team_size, body.message)
        await inquiries.submit(principal, inquiry)
        return SalesInquiryAnswer(status="received")

    return router

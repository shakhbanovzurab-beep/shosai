"""The person's usage section (`GET /v1/settings/usage`), in the cabinet's contract.

Weekly tokens per tier against the plan's allowance (`limit_tokens` null when unlimited),
the Monday week of the business calendar, the pack tokens left and this week's frontier
models, most used first (`settings/domain/billing-contract.ts`). Packs to buy arrive with
checkout (step 11).
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.application.people_views import PeopleViews
from shosai.features.billing.domain.plans import ModelTier
from shosai.features.identity.contracts import Principal, bearer_principal


class WeeklyLimitView(BaseModel):
    """A tier's tokens this week."""

    tier: ModelTier
    used_tokens: int
    limit_tokens: int | None


class FrontierModelView(BaseModel):
    """A frontier model's tokens this week."""

    model_id: str
    provider: str
    name: str
    used_tokens: int


class TokenPackView(BaseModel):
    """A one-off bundle of extra frontier tokens."""

    id: str
    tokens: int
    price_cents: int
    currency: str


class FrontierView(BaseModel):
    """Bought tokens left, this week's frontier models and the packs on sale."""

    extra_tokens: int
    models: list[FrontierModelView]
    packs: list[TokenPackView]


class UsageView(BaseModel):
    """The week's token usage."""

    week_start: datetime
    resets_at: datetime
    limits: list[WeeklyLimitView]
    frontier: FrontierView


def build_usage_router(views: PeopleViews, ports: PortDirectory) -> APIRouter:
    """The person's usage route."""
    router = APIRouter(prefix="/v1/settings", tags=["settings"])
    signed_in = bearer_principal(ports)

    @router.get("/usage")
    async def read_usage(principal: Annotated[Principal, Depends(signed_in)]) -> UsageView:
        """This week's tokens per tier, the packs left and the frontier models used."""
        week = await views.usage(principal)
        return UsageView(
            week_start=week.week_start,
            resets_at=week.resets_at,
            limits=[
                WeeklyLimitView(tier=use.tier, used_tokens=use.used, limit_tokens=use.limit)
                for use in week.tiers
            ],
            frontier=FrontierView(
                extra_tokens=week.packs_left,
                models=[
                    FrontierModelView(
                        model_id=f"{use.provider}/{use.model}",
                        provider=use.provider,
                        name=use.model,
                        used_tokens=use.tokens,
                    )
                    for use in week.models
                ],
                packs=[],
            ),
        )

    return router

"""Billing's tools in Leo's `account` toolset: the plan and the usage (ADR 0029; step 7).

Two read tools. Each reads only the person the run acts for — the tool context's scope,
never an id the model names — and returns numbers and codes the model explains: the
plan's limits with this month's minutes, and this week's tokens with the route the next
request of each tier takes (BL-D4). A plan's name is the admin's text, shown as data.
"""

from datetime import datetime, timedelta
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from shosai.core.agent_tools.bindings import ReadTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import ToolErrorCode, ToolResult
from shosai.core.agent_tools.spec import ToolEffect, ToolSpec
from shosai.features.billing.application.people_views import PeopleViews
from shosai.features.billing.application.tokens import TokenStanding
from shosai.features.billing.contracts import EntitlementsUnavailableError
from shosai.features.billing.domain.meters import SECONDS_IN_MINUTE, TokenLimit, TokenRoute
from shosai.features.billing.domain.plans import ModelTier
from shosai.features.identity.contracts import Principal


class NoArguments(BaseModel):
    """The tool takes no arguments: it always reads the signed-in person."""

    model_config = ConfigDict(extra="forbid")


class PlanOutput(BaseModel):
    """The person's plan in force and this month's meeting minutes."""

    plan_name: str = Field(description="The plan's name as the catalogue shows it.")
    paid: bool = Field(description="Whether the plan in force is a paid one.")
    paid_until: datetime | None = Field(description="When the paid period ends, if it ends.")
    meeting_minutes_per_month: int | None = Field(
        description="Meeting minutes a month; null means unlimited, 0 not included."
    )
    minutes_used_this_month: float = Field(description="Meeting minutes used this month.")
    minutes_reset_at: datetime = Field(description="When the monthly minutes reset, in UTC.")
    file_manager_gb: int | None = Field(description="File storage in GB; null is unlimited.")
    knowledge_base_mb: int | None = Field(
        description="Files Leo may use as knowledge, in MB; null is unlimited."
    )
    capabilities: list[str] = Field(description="Codes of the extras the plan switches on.")


class TierOutput(BaseModel):
    """One model tier's tokens this week and the route of its next request."""

    tier: ModelTier = Field(description="The model tier: standard or frontier.")
    used_tokens: int = Field(description="Tokens used this week.")
    weekly_limit: int | None = Field(description="Tokens included a week; null is unlimited.")
    next_request: TokenRoute = Field(
        description=(
            "Where the next request's tokens come from: within_allowance, from_packs, "
            "fall_back (a standard model answers) or stop."
        )
    )
    limit_reached: TokenLimit | None = Field(
        description="The limit that made it fall back or stop, if any."
    )


class UsageOutput(BaseModel):
    """This week's tokens per tier and the bought tokens left."""

    week_resets_at: datetime = Field(description="When the weekly allowances reset, in UTC.")
    tiers: list[TierOutput] = Field(description="Each model tier's use this week.")
    pack_tokens_left: int = Field(
        description="Bought frontier tokens left; spent after the weekly frontier allowance."
    )


GET_PLAN: Final = ToolSpec(
    name="account.get_plan",
    toolset="account",
    description=(
        "Read the signed-in person's plan: its name, whether it is paid and until when, its "
        "limits and extras, and the meeting minutes used this month. Use it when the person "
        "asks what their plan includes or why a feature or a meeting is not available."
    ),
    input=NoArguments,
    output=PlanOutput,
    effect=ToolEffect.READ,
    timeout=timedelta(seconds=5),
)
GET_USAGE: Final = ToolSpec(
    name="account.get_usage",
    toolset="account",
    description=(
        "Read the signed-in person's model tokens this week per tier, the bought tokens left "
        "and where the next request's tokens come from. Use it when the person asks about "
        "their limits or why a standard model answered instead of a frontier one."
    ),
    input=NoArguments,
    output=UsageOutput,
    effect=ToolEffect.READ,
    timeout=timedelta(seconds=5),
)
BILLING_TOOLS: Final = (GET_PLAN, GET_USAGE)


def person_of(context: ToolContext) -> Principal | None:
    """The person the run acts for, from the tool context's scope."""
    user_id = context.scope.user_id
    return None if user_id is None else Principal(user_id, context.scope.home, 0)


def billing_tools(
    views: PeopleViews, standing: TokenStanding
) -> tuple[ReadTool[NoArguments, PlanOutput], ReadTool[NoArguments, UsageOutput]]:
    """The bound tools of billing in the account toolset."""

    async def get_plan(_arguments: NoArguments, context: ToolContext) -> ToolResult[PlanOutput]:
        person = person_of(context)
        if person is None:
            return ToolResult.failed(ToolErrorCode.FORBIDDEN)
        try:
            found = await views.plans(person)
        except EntitlementsUnavailableError:
            return ToolResult.failed(ToolErrorCode.UNAVAILABLE)
        limits, minutes, snapshot = found.current.limits, found.minutes, found.entitled
        return ToolResult(
            PlanOutput(
                plan_name=found.current.name,
                paid=snapshot.paid,
                paid_until=snapshot.paid_until,
                meeting_minutes_per_month=limits.meeting_minutes_per_month,
                minutes_used_this_month=round(minutes.used_seconds / SECONDS_IN_MINUTE, 1),
                minutes_reset_at=minutes.resets_at,
                file_manager_gb=limits.file_manager_gb,
                knowledge_base_mb=limits.knowledge_base_mb,
                capabilities=sorted(item.value for item in found.current.capabilities),
            )
        )

    async def get_usage(_arguments: NoArguments, context: ToolContext) -> ToolResult[UsageOutput]:
        person = person_of(context)
        if person is None:
            return ToolResult.failed(ToolErrorCode.FORBIDDEN)
        try:
            week = await views.usage(person)
            routes = {
                use.tier: await standing.decision(person.home, person.user_id, use.tier)
                for use in week.tiers
            }
        except EntitlementsUnavailableError:
            return ToolResult.failed(ToolErrorCode.UNAVAILABLE)
        tiers = [
            TierOutput(
                tier=use.tier,
                used_tokens=use.used,
                weekly_limit=use.limit,
                next_request=routes[use.tier].route,
                limit_reached=routes[use.tier].reason,
            )
            for use in week.tiers
        ]
        return ToolResult(
            UsageOutput(
                week_resets_at=week.resets_at, tiers=tiers, pack_tokens_left=week.packs_left
            )
        )

    return (ReadTool(GET_PLAN, get_plan), ReadTool(GET_USAGE, get_usage))

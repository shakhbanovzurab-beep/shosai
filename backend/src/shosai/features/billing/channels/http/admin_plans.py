"""The admin's plan catalogue (`/v1/admin/plans*`), in the cabinet's contract (billing step 2).

Errors use the platform's envelope with stable codes (ADR 0008): `plan_not_found`,
`plan_slug_taken`, `plan_archived`, `plan_archived_with_subscribers`, `free_plan_locked`
and the catalogue rules' `plan_*` codes.
"""

from http import HTTPStatus
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from shosai.core.kernel.errors import AppError
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.application.catalogue import (
    Catalogue,
    CataloguePlan,
    PlanRemoval,
    RemovalResult,
)
from shosai.features.billing.channels.http.plan_models import (
    PlanDraftBody,
    PlanPatchBody,
    PlanView,
    draft_of,
    merged_draft,
    plan_of,
)
from shosai.features.billing.domain.money import PricesError
from shosai.features.billing.domain.plans import Plan, PlanRuleError
from shosai.features.identity.contracts import require_admin


class PlansView(BaseModel):
    """Every plan of the catalogue."""

    plans: list[PlanView]


class PlanDeletion(BaseModel):
    """A deleted plan and the promo codes it left, or the plan archived instead."""

    result: Literal["deleted", "archived"]
    plan: PlanView | None
    promo_codes_updated: int


def view_of(item: CataloguePlan) -> PlanView:
    """The contract's plan of a catalogue entry."""
    return PlanView(
        **draft_of(item.plan).model_dump(), id=item.id, subscribers=item.subscribers,
        archived=item.plan.archived, created_at=item.created_at, updated_at=item.updated_at,
    )  # fmt: skip


def checked(body: PlanDraftBody, *, archived: bool) -> Plan:
    """The domain plan of a draft; a broken catalogue rule is a 422 with its code."""
    try:
        return plan_of(body, archived=archived)
    except (PlanRuleError, PricesError) as error:
        raise AppError(error.code, HTTPStatus.UNPROCESSABLE_CONTENT) from error


def deletion_of(removal: PlanRemoval) -> PlanDeletion:
    """The contract's answer to a removal."""
    plan = None if removal.plan is None else view_of(removal.plan)
    result: Literal["deleted", "archived"] = (
        "archived" if removal.result is RemovalResult.ARCHIVED else "deleted"
    )
    return PlanDeletion(result=result, plan=plan, promo_codes_updated=removal.promo_codes_updated)


def build_admin_plans_router(catalogue: Catalogue, ports: PortDirectory) -> APIRouter:
    """The admin's routes over the plan catalogue."""
    router = APIRouter(
        prefix="/v1/admin/plans", tags=["admin"], dependencies=[Depends(require_admin(ports))]
    )

    @router.get("")
    async def list_plans() -> PlansView:
        """Every plan, archived ones included, in the pricing page's order."""
        return PlansView(plans=[view_of(item) for item in await catalogue.plans()])

    @router.post("", status_code=HTTPStatus.CREATED)
    async def create_plan(body: PlanDraftBody) -> PlanView:
        """A new plan; its slug must be free (409 `plan_slug_taken`)."""
        return view_of(await catalogue.create(checked(body, archived=False)))

    @router.patch("/{plan_id}")
    async def change_plan(plan_id: UUID, body: PlanPatchBody) -> PlanView:
        """Edit, archive or restore; an archived plan is edited only while restored."""

        def edit(current: Plan) -> Plan:
            archived = current.archived if body.archived is None else body.archived
            return checked(merged_draft(draft_of(current), body), archived=archived)

        return view_of(await catalogue.change(plan_id, edit))

    @router.delete("/{plan_id}")
    async def delete_plan(plan_id: UUID) -> PlanDeletion:
        """Delete a plan nobody holds, leaving promo codes; archive one with subscribers."""
        return deletion_of(await catalogue.remove(plan_id))

    return router

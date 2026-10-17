"""The admin's promo codes (`/v1/admin/promo-codes*`), in the cabinet's contract (billing step 2).

Errors use the platform's envelope with stable codes (ADR 0008): `promo_not_found`,
`promo_code_taken`, `promo_plan_unknown`, `promo_plan_archived`, `promo_limit_below_used`
and the rules' `promo_*` codes.
"""

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.application.promo_codes import CataloguePromo, PromoCodes
from shosai.features.billing.channels.http.promo_models import (
    PromoDraftBody,
    PromoPatchBody,
    PromoView,
    draft_of,
    merged_draft,
    promo_of,
    view_of,
)
from shosai.features.billing.domain.promos import PromoCode
from shosai.features.identity.contracts import require_admin


class PromoCodesView(BaseModel):
    """Every promo code, newest first."""

    promo_codes: list[PromoView]


def build_admin_promo_codes_router(codes: PromoCodes, ports: PortDirectory) -> APIRouter:
    """The admin's routes over promo codes."""
    router = APIRouter(
        prefix="/v1/admin/promo-codes",
        tags=["admin"],
        dependencies=[Depends(require_admin(ports))],
    )

    def shown(item: CataloguePromo) -> PromoView:
        return view_of(item.id, item.promo, item.created_at, codes.today())

    @router.get("")
    async def list_promo_codes() -> PromoCodesView:
        """Every code with its status today."""
        return PromoCodesView(promo_codes=[shown(item) for item in await codes.codes()])

    @router.post("", status_code=HTTPStatus.CREATED)
    async def create_promo_code(body: PromoDraftBody) -> PromoView:
        """A new code; the code must be free (409 `promo_code_taken`)."""
        return shown(await codes.create(promo_of(body)))

    @router.patch("/{promo_id}")
    async def change_promo_code(promo_id: UUID, body: PromoPatchBody) -> PromoView:
        """Edit a code; its use count stays as payments left it."""

        def edit(current: PromoCode) -> PromoCode:
            return promo_of(merged_draft(draft_of(current), body))

        return shown(await codes.change(promo_id, edit))

    @router.delete("/{promo_id}", status_code=HTTPStatus.NO_CONTENT)
    async def delete_promo_code(promo_id: UUID) -> Response:
        """Delete a code."""
        await codes.remove(promo_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    return router

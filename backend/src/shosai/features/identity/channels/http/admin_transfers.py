"""Account transfers for operators: request, read and cancel (identity plan §3.4, §6).

Owners and platform operators move an account between the homes once the legal review
(§22) is done; until then a request is 409 `transfers_closed`. A cancel works until the
directory switch.
"""

from datetime import datetime
from http import HTTPStatus
from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from shosai.core.kernel.homes import Home
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.application.transfers import Transfers, TransferView
from shosai.features.identity.contracts import Operator, OperatorRole, require_operator
from shosai.features.identity.domain.transfer import TransferStep

MOVERS: Final = (OperatorRole.OWNER, OperatorRole.PLATFORM)


class TransferRequest(BaseModel):
    """The home the account moves to."""

    model_config = ConfigDict(extra="forbid")

    to_home: Home


class Transfer(BaseModel):
    """A transfer and the step it is at."""

    id: UUID
    user_id: UUID
    from_home: Home
    to_home: Home
    step: TransferStep
    requested_at: datetime
    finished_at: datetime | None
    error_code: str | None


def transfer_of(view: TransferView) -> Transfer:
    """The answer of a transfer."""
    return Transfer(
        id=view.id, user_id=view.user_id, from_home=view.from_home, to_home=view.to_home,
        step=view.step, requested_at=view.requested_at, finished_at=view.finished_at,
        error_code=view.error_code,
    )  # fmt: skip


def build_admin_transfers_router(transfers: Transfers, ports: PortDirectory) -> APIRouter:
    """The transfer routes of owners and platform operators."""
    router = APIRouter(prefix="/v1/admin", tags=["admin"])
    mover = Annotated[Operator, Depends(require_operator(ports, *MOVERS))]

    @router.post("/users/{user_id}/transfers", status_code=HTTPStatus.ACCEPTED)
    async def request_transfer(user_id: UUID, body: TransferRequest, operator: mover) -> Transfer:
        """Queue the account's move to the other home; one open transfer per account."""
        return transfer_of(await transfers.request(operator, user_id, body.to_home))

    @router.get("/transfers/{transfer_id}")
    async def read_transfer(transfer_id: UUID, _operator: mover) -> Transfer:
        """The transfer and the step it is at."""
        return transfer_of(await transfers.view(transfer_id))

    @router.post("/transfers/{transfer_id}/cancel")
    async def cancel_transfer(transfer_id: UUID, operator: mover) -> Transfer:
        """Cancel before the directory switch; 409 `transfer_not_cancellable` after it."""
        return transfer_of(await transfers.cancel(operator, transfer_id))

    return router

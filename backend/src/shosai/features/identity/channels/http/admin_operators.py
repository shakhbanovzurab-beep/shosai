"""Operator roles for the owner: `GET`, `PUT` and `DELETE /v1/admin/operators*` (SM-12).

Only an owner changes roles; the last owner cannot lose the role. Every change leaves one
row in the EU audit log.
"""

from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import Response

from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.application.operators import Operators, OperatorView
from shosai.features.identity.contracts import Operator, OperatorRole, require_operator


class OperatorEntry(BaseModel):
    """An operator, their home and roles."""

    user_id: UUID
    home: str
    email: str
    full_name: str
    roles: list[OperatorRole]


class OperatorList(BaseModel):
    """Every operator of both homes, by name."""

    items: list[OperatorEntry]


class RolesChange(BaseModel):
    """The whole set of roles the person holds after the change."""

    model_config = ConfigDict(extra="forbid")

    roles: Annotated[list[OperatorRole], Field(min_length=1, max_length=len(OperatorRole))]


def entry_of(view: OperatorView) -> OperatorEntry:
    """The answer of an operator."""
    return OperatorEntry(
        user_id=view.user_id, home=view.home.value, email=view.email,
        full_name=view.full_name, roles=sorted(view.roles),
    )  # fmt: skip


def build_admin_operators_router(operators: Operators, ports: PortDirectory) -> APIRouter:
    """The owner's routes over operator roles."""
    router = APIRouter(prefix="/v1/admin/operators", tags=["admin"])
    owner = Annotated[Operator, Depends(require_operator(ports, OperatorRole.OWNER))]

    @router.get("")
    async def list_operators(_operator: owner) -> OperatorList:
        """Every operator and their roles."""
        return OperatorList(items=[entry_of(view) for view in await operators.everyone()])

    @router.put("/{user_id}")
    async def set_operator_roles(
        user_id: UUID, body: RolesChange, operator: owner
    ) -> OperatorEntry:
        """Give the person exactly these roles; 409 `last_owner` for the last owner."""
        view = await operators.set_roles(operator, user_id, frozenset(body.roles))
        return entry_of(view)

    @router.delete("/{user_id}", status_code=HTTPStatus.NO_CONTENT)
    async def remove_operator(user_id: UUID, operator: owner) -> Response:
        """Take every role away; 409 `last_owner` for the last owner."""
        await operators.set_roles(operator, user_id, frozenset())
        return Response(status_code=HTTPStatus.NO_CONTENT)

    return router

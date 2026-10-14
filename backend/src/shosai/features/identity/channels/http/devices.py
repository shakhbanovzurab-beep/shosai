"""The person's devices: `/v1/me/devices` (class web, the account section of Settings).

Not `/v1/me/sessions`: that path is the meetings' native route of the desktop clients.
"""

from datetime import datetime
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from starlette.responses import Response

from shosai.core.pagination.page import Page, PageParameters
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.application.devices import Device, Devices
from shosai.features.identity.contracts import Principal, bearer_principal


class DeviceView(BaseModel):
    """A signed-in device: where it signed in and when it was last used."""

    id: UUID
    client_kind: str
    device_label: str | None
    ip: str | None
    created_at: datetime
    last_used_at: datetime
    current: bool


class SignedOutElsewhere(BaseModel):
    """How many other sessions ended."""

    ended: int


def build_devices_router(devices: Devices, ports: PortDirectory) -> APIRouter:
    """The device routes of the signed-in person."""
    router = APIRouter(prefix="/v1/me/devices", tags=["me"])
    signed_in = bearer_principal(ports)

    @router.get("")
    async def list_devices(
        principal: Annotated[Principal, Depends(signed_in)], page: PageParameters
    ) -> Page[DeviceView]:
        """The live sessions, newest first; the current one is marked."""
        found = await devices.page(principal, page)
        return Page(items=[_view(device) for device in found.items], next_cursor=found.next_cursor)

    @router.delete("/{device_id}", status_code=HTTPStatus.NO_CONTENT)
    async def end_device(
        device_id: UUID, principal: Annotated[Principal, Depends(signed_in)]
    ) -> Response:
        """End one session; its device is signed out on its next request."""
        await devices.end(principal, device_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @router.post("/sign-out-others")
    async def end_other_devices(
        principal: Annotated[Principal, Depends(signed_in)],
    ) -> SignedOutElsewhere:
        """End every session except this one."""
        return SignedOutElsewhere(ended=await devices.end_others(principal))

    return router


def _view(device: Device) -> DeviceView:
    return DeviceView(
        id=device.id,
        client_kind=device.client_kind,
        device_label=device.device_label,
        ip=device.ip,
        created_at=device.created_at,
        last_used_at=device.last_used_at,
        current=device.current,
    )

"""`GET /v1/connectors/google_drive/picker` (plan §3.7): Google's Picker setup for the
cabinet, behind the person's bearer token; never a token."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from shosai.core.ports.directory import PortDirectory
from shosai.features.connectors.application.picker import DrivePicker
from shosai.features.identity.contracts import Principal, bearer_principal


class ConnectorPickerOut(BaseModel):
    """What the cabinet opens Google's Picker with."""

    developer_key: str
    app_id: str
    login_hint: str | None


def build_picker_router(picker: DrivePicker, ports: PortDirectory) -> APIRouter:
    """The Picker's setup route."""
    person = Annotated[Principal, Depends(bearer_principal(ports))]
    router = APIRouter(prefix="/v1/connectors", tags=["connectors"])

    @router.get("/google_drive/picker")
    async def drive_picker(principal: person) -> ConnectorPickerOut:
        """Google's Picker for choosing the Drive files Shosai may read."""
        config = await picker.config(principal.scope())
        return ConnectorPickerOut(
            developer_key=config.developer_key, app_id=config.app_id,
            login_hint=config.login_hint,
        )  # fmt: skip

    return router

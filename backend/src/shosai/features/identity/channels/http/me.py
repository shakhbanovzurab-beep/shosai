"""The person's profile: `GET/PATCH /v1/me`, `PUT/DELETE /v1/me/avatar` (class web).

The avatar is sent as the request body itself (`Content-Type: image/png`, `image/jpeg` or
`image/webp`, at most 1 MiB); the server decides the type by the bytes.
"""

from datetime import datetime
from http import HTTPStatus
from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from starlette.requests import Request

from shosai.core.kernel.errors import AppError
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.application.profile import ProfileChange, Profiles, ProfileView
from shosai.features.identity.application.registration import ClientFacts
from shosai.features.identity.channels.http.registration import client_facts
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.identity.domain.avatars import MAX_AVATAR_BYTES
from shosai.features.identity.domain.registration import ConsentKind

AVATAR_BODY: Final = {
    "requestBody": {
        "required": True,
        "content": {
            media: {"schema": {"type": "string", "format": "binary"}}
            for media in ("image/png", "image/jpeg", "image/webp")
        },
    }
}


class Consents(BaseModel):
    """The person's consents; personal data is withdrawn only by deleting the account."""

    personal_data: bool
    cross_border: bool
    marketing: bool
    improve_models: bool
    share_location: bool


class Me(BaseModel):
    """The signed-in person as Settings shows them."""

    id: UUID
    email: str
    full_name: str
    display_name: str | None
    work_role: str | None
    avatar_url: str | None
    language: str
    timezone: str | None
    country: str | None
    home: str
    consents: Consents
    created_at: datetime


class ConsentsPatch(BaseModel):
    """The consents to change; personal data is not among them."""

    model_config = ConfigDict(extra="forbid")

    cross_border: bool | None = None
    marketing: bool | None = None
    improve_models: bool | None = None
    share_location: bool | None = None


class MePatch(BaseModel):
    """The fields to change; a field left out keeps its value, `null` clears it."""

    model_config = ConfigDict(extra="forbid")

    full_name: Annotated[str | None, Field(max_length=80)] = None
    display_name: Annotated[str | None, Field(max_length=80)] = None
    work_role: Annotated[str | None, Field(max_length=32)] = None
    language: Annotated[str | None, Field(max_length=16)] = None
    timezone: Annotated[str | None, Field(max_length=64)] = None
    consents: ConsentsPatch | None = None
    # Отзыв трансграничного согласия — только после показанного предупреждения (ID-D2).
    cross_border_warning_confirmed: bool = False


def me_of(view: ProfileView) -> Me:
    """The answer of a profile."""
    user = view.user
    consents = {kind.value: value for kind, value in view.consents.items()}
    return Me(
        id=user.id, email=user.email, full_name=user.full_name, display_name=user.display_name,
        work_role=user.work_role, avatar_url=view.avatar_url, language=user.language,
        timezone=user.timezone, country=user.country, home=view.home.value,
        consents=Consents.model_validate(consents), created_at=user.created_at,
    )  # fmt: skip


def build_me_router(profiles: Profiles, ports: PortDirectory) -> APIRouter:
    """The profile routes of the signed-in person."""
    router = APIRouter(prefix="/v1/me", tags=["me"])
    signed_in = bearer_principal(ports)
    person = Annotated[Principal, Depends(signed_in)]

    @router.get("")
    async def read_me(principal: person) -> Me:
        """The profile, the consents and a 15-minute link to the avatar."""
        return me_of(await profiles.read(principal))

    @router.patch("")
    async def change_me(
        body: MePatch, principal: person, client: Annotated[ClientFacts, Depends(client_facts)]
    ) -> Me:
        """Change names, role, language, time zone or consents."""
        consents = body.consents.model_dump(exclude_none=True) if body.consents else {}
        change = ProfileChange(
            names=frozenset(body.model_fields_set - {"consents", "cross_border_warning_confirmed"}),
            full_name=body.full_name, display_name=body.display_name, work_role=body.work_role,
            language=body.language, timezone=body.timezone,
            consents={ConsentKind(kind): value for kind, value in consents.items()},
            warning_confirmed=body.cross_border_warning_confirmed,
        )  # fmt: skip
        return me_of(await profiles.change(principal, change, client))

    @router.put("/avatar", openapi_extra=AVATAR_BODY)
    async def set_avatar(request: Request, principal: person) -> Me:
        """Replace the avatar with the image in the body."""
        return me_of(await profiles.set_avatar(principal, await _body(request)))

    @router.delete("/avatar")
    async def remove_avatar(principal: person) -> Me:
        """Remove the avatar."""
        return me_of(await profiles.remove_avatar(principal))

    return router


async def _body(request: Request) -> bytes:
    """The request body, refused as soon as it grows past the avatar limit."""
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > MAX_AVATAR_BYTES:
            raise AppError("avatar_too_large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
    return bytes(data)

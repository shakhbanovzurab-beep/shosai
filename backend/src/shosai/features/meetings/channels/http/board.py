"""The room's board: `/v1/meetings/rooms/{room_id}/board` with the room pass (MR-D13).

`GET` reads the scene with its version, 0 before the first save; `PUT` keeps a scene made on
the board's version and answers the next one; `POST …/picture` answers a link to `PUT` the
board's PNG of the declared size straight into the owner's storage. Errors: `room_pass_invalid`
(401), `removed` (403), `room_finished` (410), `room_not_found` for a pass of another room
(404), `no_live_call` (409) for a save or a picture, `scene_stale` (409 with the current
`version`), `scene_too_large` and `storage_limit` (413), `rate_limited` (429 with its wait).
"""

import json
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Response
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from shosai.features.meetings.application.board import Boards, BoardScene, SceneDraft
from shosai.features.meetings.application.passes import PassCheck
from shosai.features.meetings.contracts import RoomNotFoundError
from shosai.features.meetings.domain.board import ELEMENTS_MAX, PICTURE_BYTES_MAX
from shosai.features.meetings.infrastructure.room_passes import PassHolder

RoomPassHeader = Annotated[
    str | None,
    Header(alias="X-Room-Pass", description="The room pass the join gave this session."),
]


class Strict(BaseModel):
    """A request body: a field the contract does not know is refused."""

    model_config = ConfigDict(extra="forbid")


class Out(BaseModel):
    """A response shape: every field is always sent."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class MeetingBoardOut(Out):
    """The room's scene as the editor saved it, with its version; 0 and empty before a save."""

    elements: list[JsonValue] = Field(description="The editor's elements, kept as sent.")
    files: dict[str, JsonValue] = Field(description="The editor's images by their id.")
    version: int
    updated_at: datetime | None


class MeetingBoardIn(Strict):
    """A scene to keep, made on the board's `version`."""

    elements: list[JsonValue] = Field(description=f"At most {ELEMENTS_MAX} elements.")
    files: dict[str, JsonValue]
    version: int = Field(ge=0, description="The version the scene was made on.")


class MeetingBoardSavedOut(Out):
    """The board's version after the save."""

    version: int


class MeetingBoardPictureIn(Strict):
    """The PNG's exact size in bytes."""

    size_bytes: int = Field(ge=1, le=PICTURE_BYTES_MAX)


class MeetingBoardPictureOut(Out):
    """A link to `PUT` the PNG to, with exactly these headers, until it expires."""

    method: str
    url: str
    headers: dict[str, str]
    expires_at: datetime


def scene_response(scene: BoardScene) -> Response:
    """The scene's JSON as the table holds it, wrapped without being parsed again."""
    stamp = json.dumps(None if scene.updated_at is None else scene.updated_at.isoformat())
    body = (
        f'{{"elements":{scene.elements_json},"files":{scene.files_json},'
        f'"version":{scene.version},"updated_at":{stamp}}}'
    )
    return Response(body, media_type="application/json")


def build_board_router(boards: Boards, check: PassCheck) -> APIRouter:
    """The room's board, for everyone with a room pass."""
    router = APIRouter(prefix="/v1/meetings/rooms/{room_id}/board", tags=["meetings"])

    async def holder_of(room_id: UUID, room_pass: str | None) -> PassHolder:
        holder = await check.holder(room_pass)
        if holder.room_id != room_id:
            raise RoomNotFoundError
        return holder

    # Сцена до 12 МиБ отдаётся текстом JSON из таблицы: модель ответа описывает её в OpenAPI.
    @router.get("", response_model=MeetingBoardOut)
    async def get_meeting_board(room_id: UUID, room_pass: RoomPassHeader = None) -> Response:
        """The room's board: its scene and version."""
        return scene_response(await boards.scene(await holder_of(room_id, room_pass)))

    @router.put("")
    async def save_meeting_board(
        room_id: UUID, body: MeetingBoardIn, room_pass: RoomPassHeader = None
    ) -> MeetingBoardSavedOut:
        """Keep the scene made on the board's version."""
        holder = await holder_of(room_id, room_pass)
        draft = SceneDraft(elements=body.elements, files=body.files, version=body.version)
        return MeetingBoardSavedOut(version=await boards.save(holder, draft))

    @router.post("/picture")
    async def upload_meeting_board_picture(
        room_id: UUID, body: MeetingBoardPictureIn, room_pass: RoomPassHeader = None
    ) -> MeetingBoardPictureOut:
        """A link to upload the board's PNG into the room owner's storage."""
        holder = await holder_of(room_id, room_pass)
        link = await boards.picture(holder, body.size_bytes)
        return MeetingBoardPictureOut(
            method=link.method, url=link.url, headers=dict(link.headers),
            expires_at=link.expires_at,
        )  # fmt: skip

    return router

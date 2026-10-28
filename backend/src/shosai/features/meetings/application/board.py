"""The room's board over its routes and at the call's end (MR-D13, meetings plan §3.5 flow 3).

Everyone with the room's pass reads the scene. A save needs a call going on (`no_live_call`),
the version the board still has (`scene_stale` with the current one) and the board's limits
(`scene_too_large`, which the table's bounds answer too); one participant saves at a time, so
the version only guards a change of saver. The scene is read back as the table holds its JSON
and written as one JSON text per column, so the API never builds a large board's objects
twice. The picture is a link to PUT a PNG of the declared size at the owner's file key of the
call's picture: one id per call, replaced by every upload, offered while the owner's storage
has room for it. The call's handover files the last upload in the owner's File Manager.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Final
from uuid import UUID

from pydantic import JsonValue
from pydantic_core import to_json
from sqlalchemy import Text, cast, literal, select, update
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import TypedReturnsRows

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.core.storage.port import ObjectStorage, PresignedRequest
from shosai.core.web.rate_limit import RateLimitedError
from shosai.features.files.contracts.written_files import WRITTEN_FILES, WrittenFile
from shosai.features.meetings.application.handover import CallTask
from shosai.features.meetings.domain.board import (
    PICTURE_TYPE,
    PICTURES_PER_MINUTE,
    SAVES_PER_MINUTE,
    SceneSize,
    fits,
    picture_name,
)
from shosai.features.meetings.domain.calls import CallState
from shosai.features.meetings.infrastructure.call_records import RoomWhiteboardRecord
from shosai.features.meetings.infrastructure.room_passes import PassHolder
from shosai.features.meetings.infrastructure.room_records import RoomCallRecord, RoomRecord

CHECK_VIOLATION: Final = "23514"
BOUNDS: Final = frozenset(
    f"ck_room_whiteboards_{name}" for name in ("elements_count", "elements_size", "files_size")
)
SAVE_RATE: Final = RateLimit(
    "meetings_board_save", rate=SAVES_PER_MINUTE, period=timedelta(minutes=1), burst=10
)
PICTURE_RATE: Final = RateLimit(
    "meetings_board_picture", rate=PICTURES_PER_MINUTE, period=timedelta(minutes=1), burst=3
)


@dataclass(frozen=True, slots=True)
class BoardScene:
    """The room's scene as JSON texts, its version and when it was saved; 0 before any save."""

    elements_json: str
    files_json: str
    version: int
    updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class SceneDraft:
    """A save: the editor's elements and images, and the version it was made on."""

    elements: Sequence[JsonValue]
    files: Mapping[str, JsonValue]
    version: int


EMPTY: Final = BoardScene("[]", "{}", 0, None)


def scope_of(holder: PassHolder) -> TenancyScope:
    """The room owner's scope in the room's space."""
    return TenancyScope(holder.home, holder.owner_id, holder.org_id)


def too_large() -> AppError:
    """A scene over the board's limits."""
    return AppError("scene_too_large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)


def no_live_call() -> AppError:
    """The room has no call going on."""
    return AppError("no_live_call", HTTPStatus.CONFLICT)


def breaks_bounds(error: IntegrityError) -> bool:
    """Whether the write broke one of the table's bounds on the scene's size."""
    origin = error.orig
    diag = getattr(origin, "diag", None)
    return (
        getattr(origin, "sqlstate", None) == CHECK_VIOLATION
        and getattr(diag, "constraint_name", None) in BOUNDS
    )


class Boards:
    """The boards of rooms in every home."""

    def __init__(
        self,
        transactions: HomeTransactions,
        services: tuple[PortDirectory, RateLimiter, Mapping[Home, ObjectStorage]],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports, self._limiter, self._objects = services
        self._clock = clock

    async def scene(self, holder: PassHolder) -> BoardScene:
        """The room's scene as the table holds it."""
        async with self._transactions.begin(scope_of(holder), read_only=True) as session:
            row = (
                await session.execute(
                    select(
                        cast(RoomWhiteboardRecord.elements, Text),
                        cast(RoomWhiteboardRecord.files, Text),
                        RoomWhiteboardRecord.version,
                        RoomWhiteboardRecord.updated_at,
                    ).where(RoomWhiteboardRecord.room_id == holder.room_id)
                )
            ).first()
        return EMPTY if row is None else BoardScene(*row)

    async def save(self, holder: PassHolder, draft: SceneDraft) -> int:
        """Keep the scene made on the board's version; the new version."""
        elements, files = to_json(draft.elements).decode(), to_json(draft.files).decode()
        if not fits(SceneSize(len(draft.elements), len(elements.encode()), len(files.encode()))):
            raise too_large()
        await self._admit(SAVE_RATE, holder)
        async with self._transactions.begin(scope_of(holder)) as session:
            if await self._live_call(session, holder.room_id, lock=False) is None:
                raise no_live_call()
            values = {
                "elements": cast(literal(elements, Text), JSONB),
                "files": cast(literal(files, Text), JSONB),
                "updated_by": holder.principal,
                "updated_at": self._clock(),
            }
            try:
                saved = await session.scalar(self._write(holder, draft.version, values))
            except IntegrityError as error:
                if breaks_bounds(error):
                    raise too_large() from error
                raise
            if saved is None:
                current = await session.scalar(
                    select(RoomWhiteboardRecord.version).where(
                        RoomWhiteboardRecord.room_id == holder.room_id
                    )
                )
                params = {"version": current or 0}
                raise AppError("scene_stale", HTTPStatus.CONFLICT, params=params)
        return saved

    async def picture(self, holder: PassHolder, size_bytes: int) -> PresignedRequest:
        """A link to upload the board's picture of exactly this size into the owner's storage."""
        await self._admit(PICTURE_RATE, holder)
        written = self._ports.get(WRITTEN_FILES)
        left = await written.bytes_left(holder.home, holder.owner_id)
        if left is not None and left < size_bytes:
            raise AppError("storage_limit", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        async with self._transactions.begin(scope_of(holder)) as session:
            call = await self._live_call(session, holder.room_id, lock=True)
            if call is None:
                raise no_live_call()
            if call.board_upload_id is None:
                call.board_upload_id = new_id()
            picture_id = call.board_upload_id
        key = written.key_for(holder.owner_id, picture_id)
        return await self._objects[holder.home].presign_put(
            key, content_type=PICTURE_TYPE, content_length=size_bytes
        )

    async def file_picture(self, task: CallTask) -> None:
        """The finished call's last picture as the owner's File Manager file, once."""
        async with self._transactions.begin(task.scope(), read_only=True) as session:
            row = (
                await session.execute(
                    select(
                        RoomCallRecord.board_upload_id,
                        RoomCallRecord.owner_id,
                        RoomCallRecord.started_at,
                        RoomRecord.title,
                    )
                    .join(RoomRecord, RoomRecord.id == RoomCallRecord.room_id)
                    .where(RoomCallRecord.id == task.call_id)
                )
            ).first()
        if row is None or row.board_upload_id is None:
            return
        written = self._ports.get(WRITTEN_FILES)
        info = await self._objects[task.home].head(
            written.key_for(row.owner_id, row.board_upload_id)
        )
        if info is None:
            return
        picture = WrittenFile(
            file_id=row.board_upload_id, user_id=row.owner_id,
            name=picture_name(row.title, row.started_at), content_type=PICTURE_TYPE,
            size_bytes=info.size,
        )  # fmt: skip
        async with self._transactions.begin(task.scope()) as session:
            await written.adopt(session, picture)

    def _write(
        self, holder: PassHolder, based_on: int, values: dict[str, object]
    ) -> TypedReturnsRows[int]:
        """The save as one statement: the first scene, or the next version of this one."""
        if based_on == 0:
            first = insert(RoomWhiteboardRecord).values(
                room_id=holder.room_id, owner_id=holder.owner_id, org_id=holder.org_id,
                version=1, **values,
            )  # fmt: skip
            # Сцена передаётся один раз: обновление берёт её из вставляемой строки.
            taken = {name: first.excluded[name] for name in values}
            return first.on_conflict_do_update(
                index_elements=[RoomWhiteboardRecord.room_id],
                set_={**taken, "version": RoomWhiteboardRecord.version + 1},
                where=RoomWhiteboardRecord.version == 0,
            ).returning(RoomWhiteboardRecord.version)
        return (
            update(RoomWhiteboardRecord)
            .where(
                RoomWhiteboardRecord.room_id == holder.room_id,
                RoomWhiteboardRecord.version == based_on,
            )
            .values(version=RoomWhiteboardRecord.version + 1, **values)
            .returning(RoomWhiteboardRecord.version)
        )

    async def _live_call(
        self, session: AsyncSession, room_id: UUID, *, lock: bool
    ) -> RoomCallRecord | None:
        statement = select(RoomCallRecord).where(
            RoomCallRecord.room_id == room_id, RoomCallRecord.state == CallState.LIVE.value
        )
        return await session.scalar(statement.with_for_update() if lock else statement)

    async def _admit(self, limit: RateLimit, holder: PassHolder) -> None:
        decision = await self._limiter.check(limit, f"{holder.room_id}:{holder.principal}")
        if not decision.allowed:
            raise RateLimitedError(decision.retry_after)

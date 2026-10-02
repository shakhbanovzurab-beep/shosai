"""Video rooms of the `lead` persona beyond the calendar ones, and the LiveKit admin log.

The end-to-end encrypted room (`e2ee`) has no recording and no AI assistant. The closed
room (`closed`) holds a stuck recording: the administrator's section shows it as stuck
for N minutes. The Acme room (`acme`) has a ready recording and a failed one; none is
active, so the record button is idle.

In production a ready recording creates a file in the storage root and a new meeting.
The seed puts the file there the same way but creates no meeting: the ticker counts
every meeting in the database.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from meetassist.models.room import Room
from meetassist.models.room_recording import RoomRecording
from meetassist.models.storage import StorageFile
from meetassist.models.user import User
from meetassist.models.video_admin_action import VideoAdminAction
from sqlalchemy.ext.asyncio import AsyncSession

from stable_ids import ROOM_INVITES, ROOMS

#: Журнал вмешательств: действие, комната, цель, egress, исход, пояснение, часов назад.
_AUDIT = (
    ("remove_participant", "r-parity-acme", "guest-0123456789ab", None, "ok", None, 2),
    ("close_room", "r-parity-old", None, None, "failed", "SFU не ответил", 50),
    ("stop_recording", "r-parity-old", None, "EG_parity_old", "ok", None, 70),
)


async def seed_rooms(db: AsyncSession, owner: User, admin: User, clock: datetime) -> None:
    """Seed the rooms, the recordings and the intervention log."""
    db.add_all([
        Room(id=ROOMS["e2ee"], owner_id=owner.id, name="Юристы (E2EE)", lk_room_name="r-parity-e2ee",
             invite_token=ROOM_INVITES["e2ee"], status="active", e2ee=True, created_at=clock - timedelta(days=1, hours=2)),
        Room(id=ROOMS["closed"], owner_id=owner.id, name="Планёрка июня", lk_room_name="r-parity-old",
             invite_token=ROOM_INVITES["closed"], status="closed", closed_at=clock - timedelta(days=2),
             created_at=clock - timedelta(days=20)),
    ])
    await db.flush()
    ready = StorageFile(owner_id=owner.id, name="Созвон с Acme.mp4", is_folder=False, s3_key="parity/rec-acme-ready",
                        size=187_000_000, mime_type="video/mp4", created_at=clock - timedelta(days=2, hours=1))
    db.add(ready)
    await db.flush()
    db.add_all([
        RoomRecording(owner_id=owner.id, room_id=ROOMS["acme"], egress_id="EG_parity_ready",
                      s3_key="parity/rec-acme-ready", status="ready", size=ready.size, duration_seconds=2820,
                      storage_file_id=ready.id, created_at=clock - timedelta(days=2, hours=2)),
        RoomRecording(owner_id=owner.id, room_id=ROOMS["acme"], egress_id="EG_parity_failed",
                      s3_key="parity/rec-acme-failed", status="failed", size=0, created_at=clock - timedelta(days=5)),
        # Зависшая: «идёт» дольше часа, а egress у SFU нет.
        RoomRecording(owner_id=owner.id, room_id=ROOMS["closed"], egress_id="EG_parity_stuck",
                      s3_key="parity/rec-old-stuck", status="recording", size=0, created_at=clock - timedelta(hours=3)),
    ])
    for action, room, target, egress, result, detail, hours in _AUDIT:
        db.add(VideoAdminAction(admin_id=admin.id, admin_email=admin.email, action=action, lk_room=room,
                                owner_id=owner.id, target_identity=target, egress_id=egress, result=result,
                                detail=detail, created_at=clock - timedelta(hours=hours)))
    await db.flush()

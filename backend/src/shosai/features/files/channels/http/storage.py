"""The person's storage for the File Manager's meter and banner (`GET /v1/files/storage`).

Over the limit (FL-D2) the answer carries since when and the date the newest files over
the limit go; the same for the bytes Leo uses against the knowledge limit (FL-D10), with
the date Leo stops reading the newest files over it. Unknown entitlements answer 503.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from shosai.core.ports.directory import PortDirectory
from shosai.features.files.application.leo_watch import LeoWatch
from shosai.features.files.application.quota_watch import QuotaWatch
from shosai.features.identity.contracts import Principal, bearer_principal


class StorageOut(BaseModel):
    """What the person holds against what the plan allows; a null limit is unlimited."""

    used_bytes: int
    limit_bytes: int | None
    over_limit_since: datetime | None
    removal_at: datetime | None
    leo_used_bytes: int
    leo_limit_bytes: int | None
    leo_over_limit_since: datetime | None
    leo_removal_at: datetime | None


def build_storage_router(watches: tuple[QuotaWatch, LeoWatch], ports: PortDirectory) -> APIRouter:
    """The person's storage route."""
    watch, leo_watch = watches
    router = APIRouter(prefix="/v1/files", tags=["files"])
    signed_in = bearer_principal(ports)

    @router.get("/storage")
    async def read_storage(principal: Annotated[Principal, Depends(signed_in)]) -> StorageOut:
        """Used bytes, the plan's limits and, over them, the dates files over them go."""
        standing = await watch.standing(principal.home, principal.user_id)
        leo = await leo_watch.standing(principal.home, principal.user_id)
        return StorageOut(
            used_bytes=standing.used_bytes, limit_bytes=standing.limit_bytes,
            over_limit_since=standing.over_limit_since, removal_at=standing.removal_at,
            leo_used_bytes=leo.used_bytes, leo_limit_bytes=leo.limit_bytes,
            leo_over_limit_since=leo.over_limit_since, leo_removal_at=leo.removal_at,
        )  # fmt: skip

    return router

"""Object keys of files' bytes (ADR 0055; ADR 0044, 0006).

A person's file is `u/{user_id}/f/{file_id}`, a workspace's `o/{org_id}/f/{file_id}`, an
object files holds for another slice `…/h/{id}` and its preview `…/p/{id}` (ADR 0064), an
upload another slice claims `transient/{purpose}/{upload_id}`. A key never names the home
or the file's name — `Content-Disposition` carries the name — and always the full owner
id, so a person's v2 objects share one prefix. A draft key is kept verbatim in its pointer
and never parsed for an owner.
"""

from dataclasses import dataclass
from typing import Final
from uuid import UUID

from shosai.core.storage.keys import check_object_key
from shosai.features.files.domain.purposes import UploadPurpose

PERSON_PREFIX: Final = "u/"
WORKSPACE_PREFIX: Final = "o/"
TRANSIENT_PREFIX: Final = "transient/"


@dataclass(frozen=True, slots=True)
class PersonOwner:
    """A file of a person."""

    user_id: UUID


@dataclass(frozen=True, slots=True)
class WorkspaceOwner:
    """A file of a workspace."""

    org_id: UUID


type Owner = PersonOwner | WorkspaceOwner


def owner_prefix(owner: Owner) -> str:
    """The prefix of every v2 object of an owner: `u/{user_id}/` or `o/{org_id}/`."""
    if isinstance(owner, PersonOwner):
        return f"{PERSON_PREFIX}{owner.user_id}/"
    return f"{WORKSPACE_PREFIX}{owner.org_id}/"


def file_key(owner: Owner, file_id: UUID) -> str:
    """The key of a file's bytes in its owner's prefix."""
    return check_object_key(f"{owner_prefix(owner)}f/{file_id}")


def held_key(owner: Owner, held_id: UUID) -> str:
    """The key of an object files holds for another slice, in its owner's prefix."""
    return check_object_key(f"{owner_prefix(owner)}h/{held_id}")


def preview_key(owner: Owner, held_id: UUID) -> str:
    """The key of a held image's preview."""
    return check_object_key(f"{owner_prefix(owner)}p/{held_id}")


def transient_key(purpose: UploadPurpose, upload_id: UUID) -> str:
    """The key of an upload another slice claims; bucket rules expire it after 3 days."""
    return check_object_key(f"{TRANSIENT_PREFIX}{purpose.value}/{upload_id}")

"""Identity's batch of names for the tests' fake profile readers: each person's profile name."""

from collections.abc import Awaitable, Callable, Collection, Mapping
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.identity.contracts import AccountProfile

type ProfileOf = Callable[[AsyncSession, UUID], Awaitable[AccountProfile | None]]


async def names_by_profile(
    profile: ProfileOf, session: AsyncSession, user_ids: Collection[UUID]
) -> Mapping[UUID, str]:
    """The display name of each person a fake's `profile` knows."""
    found: dict[UUID, str] = {}
    for user_id in user_ids:
        known = await profile(session, user_id)
        if known is not None:
            found[user_id] = known.display_name
    return found

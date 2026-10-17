"""The month's recorded minutes while no meeting is recorded in Shosai yet.

Billing's step 4 counts minutes from `usage_events` and the meetings port; until meetings
record anything, every person has used none of their month.
"""

from datetime import datetime
from uuid import UUID

from shosai.core.kernel.homes import Home


class NoMeetingsYet:
    """Recorded seconds before any meeting exists: none."""

    async def used_seconds(self, home: Home, user_id: UUID, since: datetime) -> int:
        """Zero for every person and month."""
        del home, user_id, since
        return 0

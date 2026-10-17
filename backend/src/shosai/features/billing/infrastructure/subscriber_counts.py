"""Subscriber counts of the catalogue while billing holds no subscriptions.

Subscriptions arrive with billing's step 3, which binds the counter over both homes in
this one's place; until then nobody holds a plan, so every plan can be deleted.
"""

from collections.abc import Collection, Mapping
from uuid import UUID


class NoSubscriptions:
    """The counter of a catalogue that no subscription references."""

    async def counts(self, plan_ids: Collection[UUID]) -> Mapping[UUID, int]:
        """Zero for every plan."""
        return dict.fromkeys(plan_ids, 0)

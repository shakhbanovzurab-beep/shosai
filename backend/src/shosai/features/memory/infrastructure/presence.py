"""The "has memories" bit in Valkey (Leo §10; the draft's lesson of 50e4bbaa4).

A person with no current fact costs a turn no embedding call: recall reads the bit first. It
is set when a current fact is written and cleared when none is left; it lives a day, and a
missing bit is read as "yes", so a lost key costs one call and a database read, never a fact.
"""

from typing import Final
from uuid import UUID

PREFIX: Final = "memory:has:"
TTL_SECONDS: Final = 24 * 60 * 60


def has_memories_key(user_id: UUID) -> str:
    """The person's bit."""
    return f"{PREFIX}{user_id}"

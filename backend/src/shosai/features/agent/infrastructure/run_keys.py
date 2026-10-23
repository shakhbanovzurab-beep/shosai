"""Where a run's in-flight state lives in Valkey (Leo §10, ADR 0024): fixed keys, no scans.

A thread has its lease; a run has its event log and its checkpoint, one key each, so erasing
a person's runs deletes known keys and never walks the keyspace. Everything here lives
minutes to an hour and is never the source of truth: the database is.
"""

from typing import Final
from uuid import UUID

PREFIX: Final = "agent"


def lease_key(thread_id: UUID) -> str:
    """The thread's lease: one active run per thread."""
    return f"{PREFIX}:lease:{thread_id}"


def log_key(run_id: UUID) -> str:
    """The run's event log, a stream any API process can resume from."""
    return f"{PREFIX}:run:{run_id}:log"


def checkpoint_key(run_id: UUID) -> str:
    """The run's checkpoint while it is active or paused: one hash of references."""
    return f"{PREFIX}:run:{run_id}:ckpt"


def run_keys(run_id: UUID) -> tuple[str, str]:
    """Every key of a run."""
    return log_key(run_id), checkpoint_key(run_id)

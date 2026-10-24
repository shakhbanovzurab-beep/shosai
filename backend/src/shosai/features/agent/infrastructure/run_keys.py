"""Where a run's in-flight state lives in Valkey (Leo §10, ADR 0024, AG-D12): fixed keys, no scans.

A thread has its lease; a run has its event log, its stop request and its checkpoint, one key
each, so erasing a person's runs deletes known keys and never walks the keyspace. The fleet
keeps sorted sets scored by the moment a member lapses: the runs admitted and not yet over,
the same per person, and the agent workers alive. Everything here lives minutes to an hour
and is never the source of truth: the database is.
"""

from typing import Final
from uuid import UUID

from shosai.core.kv.keys import build_key

PURPOSE: Final = "agent"
FLEET_RUNS: Final = build_key(PURPOSE, "fleet", "runs")
FLEET_WORKERS: Final = build_key(PURPOSE, "fleet", "workers")


def lease_key(thread_id: UUID) -> str:
    """The thread's lease: one active run per thread, its value the run's id."""
    return build_key(PURPOSE, "lease", str(thread_id))


def log_key(run_id: UUID) -> str:
    """The run's event log, a stream any API process can resume from."""
    return build_key(PURPOSE, "run", str(run_id), "log")


def stop_key(run_id: UUID) -> str:
    """The person asked the run to stop: "Stop", a superseding turn or a deleted thread."""
    return build_key(PURPOSE, "run", str(run_id), "stop")


def checkpoint_key(run_id: UUID) -> str:
    """The run's checkpoint while it is active or paused: one hash of references."""
    return build_key(PURPOSE, "run", str(run_id), "ckpt")


def person_runs_key(user_id: UUID) -> str:
    """The person's admitted runs not yet over, at most two (Leo §12)."""
    return build_key(PURPOSE, "person", str(user_id), "runs")


def wake_key(reader: str) -> str:
    """The stream an API process's log reader also waits on, so a new follower wakes it."""
    return build_key(PURPOSE, "wake", reader)


def run_keys(run_id: UUID) -> tuple[str, str, str]:
    """Every key of a run."""
    return log_key(run_id), stop_key(run_id), checkpoint_key(run_id)

"""An effect runs once per key; a repeat returns its outcome and writes nothing (§10, inv-9)."""

import asyncio
import uuid
from datetime import timedelta

import pytest
import sqlalchemy as sa
from prometheus_client import CollectorRegistry

from shosai.core.idempotency.errors import (
    IdempotencyKeyReusedError,
    ReadOnlyEffectTransactionError,
)
from shosai.core.idempotency.ledger import (
    EffectKey,
    EffectLedger,
    EffectScope,
    account_key,
    fingerprint_of,
)
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.idempotency.purge import EffectKeyPurge
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from tests.core.idempotency.ledger_bench import NOTES, NoteWriter, NoteWritten
from tests.harness.connections import fetch_rows, fetch_value
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

USER_ID = uuid.UUID("0190f0f0-0000-7000-8000-00000000000a")


class EffectFailedError(Exception):
    """The probe effect failed after writing its row."""


def ledger() -> tuple[EffectLedger, EffectKeyMetrics, CollectorRegistry]:
    """A ledger with its own metrics registry."""
    registry = CollectorRegistry()
    metrics = EffectKeyMetrics(registry)
    return EffectLedger(metrics), metrics, registry


async def write_once(
    homes: DatabaseAccess, effects: EffectLedger, writer: NoteWriter, key: EffectKey
) -> tuple[NoteWritten, bool]:
    """One transaction that applies the probe effect under the key."""
    async with homes.transactions.begin(TenancyScope(Home.RU, USER_ID)) as session:
        result = await effects.once(session, key, NoteWritten, lambda: writer.write(session))
    return result.outcome, result.replayed


async def test_a_replayed_key_returns_the_stored_outcome_and_writes_nothing(
    homes: DatabaseAccess, probe_table: sa.TableClause, run_slot: RunSlot
) -> None:
    effects, _, registry = ledger()
    writer = NoteWriter()
    key = EffectKey(
        NOTES,
        account_key(USER_ID, "retry-1"),
        fingerprint_of(NoteWritten(note_id=uuid.UUID(int=1))),
    )

    first, first_replayed = await write_once(homes, effects, writer, key)
    second, second_replayed = await write_once(homes, effects, writer, key)

    connection = run_slot.claimed.connections[Home.RU]
    assert (first_replayed, second_replayed) == (False, True)
    assert second == first
    assert writer.runs == 1
    assert await fetch_value(connection, "SELECT count(*) FROM probe_records") == 1
    [row] = await fetch_rows(connection, "SELECT scope, key, user_id, outcome FROM effect_keys")
    assert (row["scope"], row["key"], row["user_id"]) == (NOTES.name, key.key, USER_ID)
    assert row["outcome"] == {"note_id": str(first.note_id)}
    labels = {"scope": NOTES.name, "outcome": "replayed"}
    assert registry.get_sample_value("shosai_effect_key_repeats_total", labels) == 1


async def test_the_same_key_with_another_request_is_refused_and_writes_nothing(
    homes: DatabaseAccess, probe_table: sa.TableClause, run_slot: RunSlot
) -> None:
    effects, _, _ = ledger()
    writer = NoteWriter()
    await write_once(homes, effects, writer, EffectKey(NOTES, "k", "a" * 64))

    with pytest.raises(IdempotencyKeyReusedError):
        await write_once(homes, effects, writer, EffectKey(NOTES, "k", "b" * 64))

    connection = run_slot.claimed.connections[Home.RU]
    assert writer.runs == 1
    assert await fetch_value(connection, "SELECT count(*) FROM probe_records") == 1


async def test_two_transactions_with_one_key_apply_the_effect_once(
    homes: DatabaseAccess, probe_table: sa.TableClause, run_slot: RunSlot
) -> None:
    effects, _, _ = ledger()
    writer = NoteWriter()
    key = EffectKey(NOTES, "double-click")

    results = await asyncio.gather(*(write_once(homes, effects, writer, key) for _ in range(2)))

    connection = run_slot.claimed.connections[Home.RU]
    assert sorted(replayed for _, replayed in results) == [False, True]
    assert results[0][0] == results[1][0]
    assert await fetch_value(connection, "SELECT count(*) FROM probe_records") == 1


async def test_a_failed_effect_leaves_the_key_free_for_its_retry(
    homes: DatabaseAccess, probe_table: sa.TableClause, run_slot: RunSlot
) -> None:
    effects, _, _ = ledger()
    writer = NoteWriter(failures=[EffectFailedError()])
    key = EffectKey(NOTES, "flaky")

    with pytest.raises(EffectFailedError):
        await write_once(homes, effects, writer, key)
    outcome, replayed = await write_once(homes, effects, writer, key)

    connection = run_slot.claimed.connections[Home.RU]
    assert (writer.runs, replayed) == (2, False)
    [row] = await fetch_rows(connection, "SELECT id FROM probe_records")
    assert row["id"] == outcome.note_id


async def test_an_expired_key_is_applied_again_and_the_purge_removes_only_expired_keys(
    homes: DatabaseAccess, probe_table: sa.TableClause, run_slot: RunSlot
) -> None:
    effects, metrics, registry = ledger()
    brief = EffectScope("probe.brief_note", timedelta(milliseconds=200))
    writer = NoteWriter()
    await write_once(homes, effects, writer, EffectKey(brief, "short"))
    await write_once(homes, effects, writer, EffectKey(NOTES, "long"))
    connection = run_slot.claimed.connections[Home.RU]
    await connection.execute("SELECT pg_sleep(0.25)")

    _, replayed = await write_once(homes, effects, writer, EffectKey(brief, "short"))
    await connection.execute("SELECT pg_sleep(0.25)")
    removed = await EffectKeyPurge(homes.transactions, metrics).purge(Home.RU)

    assert (replayed, writer.runs) == (False, 3)
    assert removed == 1
    keys = await fetch_rows(connection, "SELECT scope FROM effect_keys")
    assert [row["scope"] for row in keys] == [NOTES.name]
    assert registry.get_sample_value("shosai_effect_keys_purged_total", {"home": "ru"}) == 1


async def test_a_read_only_transaction_cannot_record_a_key(homes: DatabaseAccess) -> None:
    effects, _, _ = ledger()
    writer = NoteWriter()

    with pytest.raises(ReadOnlyEffectTransactionError):
        async with homes.transactions.begin(TenancyScope(Home.EU), read_only=True) as session:
            await effects.once(
                session, EffectKey(NOTES, "k"), NoteWritten, lambda: writer.write(session)
            )

    assert writer.runs == 0


@pytest.mark.parametrize(
    ("name", "keep"),
    [
        ("notes", timedelta(hours=1)),
        ("Probe.Note", timedelta(hours=1)),
        ("probe.note", timedelta(0)),
        ("probe.note", timedelta(days=91)),
    ],
)
def test_a_scope_names_its_slice_and_keeps_keys_for_a_bounded_time(
    name: str, keep: timedelta
) -> None:
    with pytest.raises(ValueError, match="ключ"):
        EffectScope(name, keep)


@pytest.mark.parametrize("key", ["", "x" * 201])
def test_a_key_is_one_to_two_hundred_characters(key: str) -> None:
    with pytest.raises(ValueError, match="ключ эффекта"):
        EffectKey(NOTES, key)


def test_a_fingerprint_does_not_depend_on_field_order() -> None:
    first = NoteWritten.model_validate({"note_id": str(uuid.UUID(int=7))})
    second = NoteWritten(note_id=uuid.UUID(int=7))

    assert fingerprint_of(first) == fingerprint_of(second)
    assert len(fingerprint_of(first)) == 64

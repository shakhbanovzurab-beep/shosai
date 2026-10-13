"""A retried request with the same `Idempotency-Key` gets the first answer and writes nothing."""

import uuid
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter
from prometheus_client import CollectorRegistry
from pydantic import BaseModel, Field

from shosai.core.idempotency.http import IDEMPOTENCY_KEY_HEADER, IdempotencyKeyHeader
from shosai.core.idempotency.ledger import EffectKey, EffectLedger, account_key, fingerprint_of
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from tests.core.idempotency.ledger_bench import NOTES, NoteWriter, NoteWritten
from tests.core.web.probe_app import build_probe_app, client_of
from tests.harness.connections import fetch_value
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

USER_ID = uuid.UUID("0190f0f0-0000-7000-8000-00000000000c")
ROUTE = "/v1/probe/notes"


class NoteRequest(BaseModel):
    """A note to write."""

    note: Annotated[str, Field(min_length=1, max_length=40)]


def notes_router(homes: DatabaseAccess) -> APIRouter:
    """A write route that applies its effect once per key of the account."""
    effects = EffectLedger(EffectKeyMetrics(CollectorRegistry()))
    router = APIRouter(prefix=ROUTE)

    @router.post("", status_code=201)
    async def write_note(body: NoteRequest, key: IdempotencyKeyHeader) -> NoteWritten:
        """Write the note once per key."""
        effect_key = EffectKey(NOTES, account_key(USER_ID, key), fingerprint_of(body))
        writer = NoteWriter(note=body.note)
        async with homes.transactions.begin(TenancyScope(Home.EU, USER_ID)) as session:
            result = await effects.once(
                session, effect_key, NoteWritten, lambda: writer.write(session)
            )
        return result.outcome

    return router


async def test_a_retried_request_returns_the_first_answer_and_writes_nothing(
    homes: DatabaseAccess, probe_table: sa.TableClause, run_slot: RunSlot
) -> None:
    probe = build_probe_app(extra=[notes_router(homes)])
    headers = {IDEMPOTENCY_KEY_HEADER: "7c1d4e0a-retry"}
    async with client_of(probe.app) as client:
        first = await client.post(ROUTE, json={"note": "draft"}, headers=headers)
        retry = await client.post(ROUTE, json={"note": "draft"}, headers=headers)
        reused = await client.post(ROUTE, json={"note": "other"}, headers=headers)

    connection = run_slot.claimed.connections[Home.EU]
    assert (first.status_code, retry.status_code) == (201, 201)
    assert retry.json() == first.json()
    assert reused.status_code == 422
    assert reused.json()["error"]["code"] == "idempotency_key_reused"
    assert await fetch_value(connection, "SELECT count(*) FROM probe_records") == 1


async def test_a_missing_or_malformed_key_is_refused_before_the_handler(
    homes: DatabaseAccess, probe_table: sa.TableClause, run_slot: RunSlot
) -> None:
    probe = build_probe_app(extra=[notes_router(homes)])
    async with client_of(probe.app) as client:
        missing = await client.post(ROUTE, json={"note": "draft"})
        spaced = await client.post(
            ROUTE, json={"note": "draft"}, headers={IDEMPOTENCY_KEY_HEADER: "two words"}
        )
        long = await client.post(
            ROUTE, json={"note": "draft"}, headers={IDEMPOTENCY_KEY_HEADER: "k" * 129}
        )

    assert [response.status_code for response in (missing, spaced, long)] == [422] * 3
    connection = run_slot.claimed.connections[Home.EU]
    assert await fetch_value(connection, "SELECT count(*) FROM probe_records") == 0


def test_openapi_declares_the_required_header(homes: DatabaseAccess) -> None:
    probe = build_probe_app(extra=[notes_router(homes)])

    operation = probe.app.openapi()["paths"][ROUTE]["post"]

    [parameter] = [item for item in operation["parameters"] if item["in"] == "header"]
    assert (parameter["name"], parameter["required"]) == (IDEMPOTENCY_KEY_HEADER, True)
    assert parameter["schema"]["maxLength"] == 128

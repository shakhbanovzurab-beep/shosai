"""Capture's part of a person's export, transfer and erasure: the voice conversations' minutes."""

import uuid
from datetime import UTC, datetime

from shosai.core.account_data.handlers import AccountRef
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.capture.application.account_data import CaptureAccountData
from shosai.features.capture.infrastructure.voice_records import VoiceSessionRecord
from tests.harness.database_access import DatabaseAccess


async def test_export_transfer_and_erasure_cover_the_conversations(homes: DatabaseAccess) -> None:
    person, other = uuid.uuid4(), uuid.uuid4()
    started = datetime.now(UTC)
    for user_id in (person, other):
        async with homes.transactions.begin(TenancyScope(Home.RU, user_id)) as session:
            session.add(
                VoiceSessionRecord(id=uuid.uuid4(), started_at=started, user_id=user_id, seconds=95)
            )
    handler = CaptureAccountData(homes.transactions)
    russian, european = AccountRef(person, Home.RU), AccountRef(person, Home.EU)

    exported = {
        item.name: b"".join([chunk async for chunk in item.chunks])
        async for item in handler.export(russian)
    }
    await handler.copy(russian, Home.EU)
    await handler.copy(russian, Home.EU)
    same = await handler.manifest(russian) == await handler.manifest(european)
    await handler.erase(russian)
    await handler.purge(european)

    assert set(exported) == {"capture_voice_sessions.jsonl"}
    assert b'"seconds": 95' in exported["capture_voice_sessions.jsonl"]
    assert str(other).encode() not in exported["capture_voice_sessions.jsonl"]
    assert same
    assert await handler.remains(russian) == ()
    assert await handler.remains(european) == ()
    assert await handler.remains(AccountRef(other, Home.RU)) == ("capture_voice_sessions",)

"""`shosai identity grant-operator`: the first owner, given from the command line (SM-12)."""

from pathlib import Path
from uuid import UUID

import pytest
from redis.asyncio import Redis

from shosai.core.kernel.homes import Home
from tests.composition.role_process import run_command
from tests.features.identity.registration_bench import DIRECTORY_KEY, registration_bench
from tests.features.identity.test_sign_in import EMAIL, account
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.process_environ import slot_environ
from tests.harness.run_slot import RunSlot
from tests.harness.settings import HarnessSettings

GRANT = ["identity", "grant-operator", "--role", "owner", "--email"]


@pytest.fixture
async def registered(
    run_slot: RunSlot, homes: DatabaseAccess, valkey: Redis, redis_cache: Redis
) -> UUID:
    """A confirmed account in the Russian home, with no operator role."""
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        return await account(bench, run_slot)


async def test_the_cli_gives_an_active_account_the_owner_role(
    run_slot: RunSlot, harness_settings: HarnessSettings, registered: UUID, tmp_path: Path
) -> None:
    environ = slot_environ(run_slot, harness_settings) | {
        "IDENTITY_DIRECTORY_HMAC_KEY": DIRECTORY_KEY.decode()
    }

    code, lines = await run_command([*GRANT, EMAIL.upper()], environ, tmp_path / "grant.log")
    unknown, refused = await run_command(
        [*GRANT, "nobody@example.com"], environ, tmp_path / "unknown.log"
    )

    connection = run_slot.claimed.connections[Home.RU]
    roles = await fetch_rows(connection, "SELECT user_id, role, granted_by FROM operator_roles")
    assert code == 0
    assert roles == [{"user_id": registered, "role": "owner", "granted_by": None}]
    assert any(line["message"] == "Роль оператора выдана" for line in lines)
    assert unknown == 1
    [line] = [line for line in refused if line["message"] == "Роль не выдана"]
    assert line["code"] == "user_not_found"

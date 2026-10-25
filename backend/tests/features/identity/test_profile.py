"""The profile, the consent journal, the avatar and Leo's account tool (step 6a)."""

import struct
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from uuid import UUID

from redis.asyncio import Redis

from shosai.core.agent_tools.context import ToolContext
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.application.profile import Profiles
from shosai.features.identity.channels.agent_tools import NoArguments, account_tools
from shosai.features.identity.domain.avatars import AvatarFormat, AvatarProblem, check_avatar
from shosai.features.identity.infrastructure.consents import ConsentJournal
from tests.core.storage.adapters import slot_storage
from tests.features.identity.registration_bench import (
    BenchOptions,
    RegistrationBench,
    registration_bench,
)
from tests.features.identity.test_sign_in import account, login
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot
from tests.harness.shared_services import SlotBucket


def png(width: int = 64, height: int = 64) -> bytes:
    header = struct.pack(">II", width, height) + b"\x08\x06\x00\x00\x00"
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + header + b"\x00" * 64


def jpeg(width: int = 100, height: int = 80) -> bytes:
    app0 = b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    frame = b"\xff\xc0\x00\x11\x08" + struct.pack(">HH", height, width) + b"\x03" + b"\x00" * 9
    return b"\xff\xd8" + app0 + frame + b"\xff\xd9"


def webp(width: int = 200, height: int = 120) -> bytes:
    canvas = (width - 1).to_bytes(3, "little") + (height - 1).to_bytes(3, "little")
    return b"RIFF\x00\x00\x00\x00WEBPVP8X\x0a\x00\x00\x00\x00\x00\x00\x00" + canvas


def test_the_bytes_decide_the_type_and_the_size() -> None:
    assert check_avatar(png()).format is AvatarFormat.PNG
    assert check_avatar(jpeg()).format is AvatarFormat.JPEG
    assert check_avatar(webp()).format is AvatarFormat.WEBP
    assert check_avatar(b"<script>alert(1)</script>").problem is AvatarProblem.NOT_AN_IMAGE
    assert check_avatar(png(2000, 2000)).problem is AvatarProblem.BAD_SIZE
    assert check_avatar(png(8, 8)).problem is AvatarProblem.BAD_SIZE
    assert check_avatar(png() + b"\x00" * (1024 * 1024)).problem is AvatarProblem.TOO_LARGE


def bearer(token: object) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def signed_in(bench: RegistrationBench, run_slot: RunSlot) -> dict[str, str]:
    await account(bench, run_slot)
    return bearer((await login(bench))["access_token"])


async def test_the_profile_shows_and_changes_the_persons_fields(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        headers = await signed_in(bench, run_slot)
        before = (await bench.http.get("/v1/me", headers=headers)).json()
        changed = await bench.http.patch(
            "/v1/me",
            headers=headers,
            json={"display_name": "Аня", "work_role": "founder", "timezone": "Europe/Moscow"},
        )
        refused = [
            await bench.http.patch("/v1/me", headers=headers, json=body)
            for body in ({"work_role": "astronaut"}, {"timezone": "Mars/Base"}, {"full_name": "  "})
        ]
        cleared = await bench.http.patch("/v1/me", headers=headers, json={"display_name": None})

    assert before["consents"] == {
        "personal_data": True, "cross_border": True, "marketing": False,
        "improve_models": False, "share_location": False,
    }  # fmt: skip
    assert (before["home"], before["country"], before["avatar_url"]) == ("ru", "RU", None)
    assert (changed.json()["display_name"], changed.json()["work_role"]) == ("Аня", "founder")
    assert [answer.json()["error"]["code"] for answer in refused] == [
        "unknown_work_role", "unknown_timezone", "blank_name",
    ]  # fmt: skip
    assert cleared.json()["display_name"] is None
    assert cleared.json()["timezone"] == "Europe/Moscow"


async def test_a_chosen_zone_is_fixed_until_the_person_picks_automatic_again(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        headers = await signed_in(bench, run_slot)
        before = (await bench.http.get("/v1/me", headers=headers)).json()
        fixed = await bench.http.patch(
            "/v1/me", headers=headers, json={"timezone": "Asia/Tokyo", "timezone_auto": False}
        )
        renamed = await bench.http.patch("/v1/me", headers=headers, json={"full_name": "Anna P."})
        unset = await bench.http.patch("/v1/me", headers=headers, json={"timezone_auto": None})
        automatic = await bench.http.patch(
            "/v1/me", headers=headers, json={"timezone": "Europe/Berlin", "timezone_auto": True}
        )

    assert before["timezone_auto"] is True
    assert (fixed.json()["timezone"], fixed.json()["timezone_auto"]) == ("Asia/Tokyo", False)
    assert (renamed.json()["timezone"], renamed.json()["timezone_auto"]) == ("Asia/Tokyo", False)
    assert (unset.status_code, unset.json()["error"]["code"]) == (422, "unknown_timezone_mode")
    assert (automatic.json()["timezone"], automatic.json()["timezone_auto"]) == (
        "Europe/Berlin", True,
    )  # fmt: skip


async def test_a_consent_change_is_one_journal_row_seen_by_the_next_reader(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        headers = await signed_in(bench, run_slot)
        user_id = (await bench.http.get("/v1/me", headers=headers)).json()["id"]
        rows_before = await consent_rows(run_slot)
        marketing = await bench.http.patch(
            "/v1/me", headers=headers, json={"consents": {"marketing": True}}
        )
        unchanged = await bench.http.patch(
            "/v1/me", headers=headers, json={"consents": {"marketing": True}}
        )
        unwarned = await bench.http.patch(
            "/v1/me", headers=headers, json={"consents": {"cross_border": False}}
        )
        warned = await bench.http.patch(
            "/v1/me",
            headers=headers,
            json={"consents": {"cross_border": False}, "cross_border_warning_confirmed": True},
        )
        scope = TenancyScope(Home.RU, new_id())
        async with homes.transactions.begin(scope, read_only=True) as session:
            consents_abroad = await ConsentJournal().cross_border(session, UUID(user_id))

    assert marketing.json()["consents"]["marketing"] is True
    assert unchanged.status_code == 200
    assert (unwarned.status_code, unwarned.json()["error"]["code"]) == (
        422, "consent_warning_required",
    )  # fmt: skip
    assert warned.json()["consents"]["cross_border"] is False
    assert consents_abroad is False
    assert await consent_rows(run_slot) == rows_before + 2


async def test_improving_the_models_is_read_by_leo_and_told_once_per_change(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        headers = await signed_in(bench, run_slot)
        user_id = UUID((await bench.http.get("/v1/me", headers=headers)).json()["id"])
        reads = []
        for wanted in (True, True, False):
            await bench.http.patch(
                "/v1/me", headers=headers, json={"consents": {"improve_models": wanted}}
            )
            async with homes.transactions.begin(
                TenancyScope(Home.RU, user_id), read_only=True
            ) as session:
                reads.append(await ConsentJournal().improve_models(session, user_id))
    told = await fetch_rows(
        run_slot.claimed.connections[Home.RU],
        "SELECT payload FROM outbox_messages WHERE event_type = 'identity.consent.changed'"
        " ORDER BY occurred_at",
    )

    assert reads == [True, True, False]
    assert [
        (row["payload"]["kind"], row["payload"]["granted"])
        for row in told
        if row["payload"]["user_id"] == str(user_id)
    ] == [("improve_models", True), ("improve_models", False)]


async def consent_rows(run_slot: RunSlot) -> int:
    rows = await fetch_rows(run_slot.claimed.connections[Home.RU], "SELECT id FROM user_consents")
    return len(rows)


async def test_the_avatar_is_an_image_by_its_bytes_and_lives_in_the_home_bucket(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis,
    buckets: Mapping[Home, SlotBucket],
) -> None:  # fmt: skip
    objects = {home: slot_storage(bucket).objects for home, bucket in buckets.items()}
    options = BenchOptions(objects=objects)
    async with registration_bench(homes.transactions, valkey, redis_cache, options) as bench:
        headers = await signed_in(bench, run_slot)
        disguised = await bench.http.put(
            "/v1/me/avatar",
            content=b"<script>alert(1)</script>",
            headers={**headers, "Content-Type": "image/png"},
        )
        huge = await bench.http.put(
            "/v1/me/avatar", content=b"\x00" * (1024 * 1024 + 1), headers=headers
        )
        stored = await bench.http.put("/v1/me/avatar", content=png(), headers=headers)
        me = await bench.http.get("/v1/auth/me", headers=headers)
        kept = [item async for item in objects[Home.RU].list_objects("avatars/")]
        removed = await bench.http.delete("/v1/me/avatar", headers=headers)
        left = [item async for item in objects[Home.RU].list_objects("avatars/")]

    assert (disguised.status_code, disguised.json()["error"]["code"]) == (422, "avatar_type")
    assert (huge.status_code, huge.json()["error"]["code"]) == (413, "avatar_too_large")
    assert stored.status_code == 200
    assert stored.json()["avatar_url"]
    assert me.json()["avatar_url"]
    assert len(kept) == 1
    assert kept[0].key.endswith(".png")
    assert removed.json()["avatar_url"] is None
    assert left == []


async def test_leo_reads_only_the_account_its_run_acts_for(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        headers = await signed_in(bench, run_slot)
        await bench.http.patch("/v1/me", headers=headers, json={"display_name": "Аня"})
        me = (await bench.http.get("/v1/me", headers=headers)).json()
        user_id = UUID(me["id"])
    profiles = Profiles(homes.transactions, ConsentJournal(), {}, EventOutbox(EventTypes([])))
    [tool] = account_tools(homes.transactions, profiles)
    deadline = datetime.now(UTC) + timedelta(seconds=5)

    mine = await tool.run(
        NoArguments(), ToolContext(TenancyScope(Home.RU, user_id), new_id(), deadline)
    )
    stranger = await tool.run(
        NoArguments(), ToolContext(TenancyScope(Home.RU, new_id()), new_id(), deadline)
    )

    assert mine.output is not None
    assert (mine.output.display_name, mine.output.language) == ("Аня", "ru")
    assert stranger.output is None
    assert stranger.error is not None
    assert stranger.error.code.value == "not_found"
    # Читатель профиля для других срезов отдаёт и адрес писем об аккаунте (files, FL-D2).
    async with homes.transactions.begin(TenancyScope(Home.RU, user_id), read_only=True) as session:
        profile = await profiles.profile(session, user_id)
    assert profile is not None
    assert profile.email == me["email"]

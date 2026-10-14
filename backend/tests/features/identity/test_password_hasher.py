"""bcrypt in its own pool; draft hashes keep verifying (ADR 0045, DATA_MAPPING §5.1)."""

import asyncio
from collections.abc import AsyncIterator

import bcrypt
import pytest_asyncio

from shosai.features.identity.infrastructure.password_hasher import PasswordHasher

# Тесты не ждут 250 мс на хеш: стоимость 4 проверяет те же пути.
TEST_ROUNDS = 4


@pytest_asyncio.fixture
async def hasher() -> AsyncIterator[PasswordHasher]:
    pool = PasswordHasher(TEST_ROUNDS, workers=2)
    try:
        yield pool
    finally:
        pool.close()


async def test_a_hash_verifies_its_password_and_no_other(hasher: PasswordHasher) -> None:
    stored = await hasher.hash("correct horse battery staple")

    assert stored.startswith("$2b$04$")
    assert await hasher.verify("correct horse battery staple", stored)
    assert not await hasher.verify("correct horse battery stapler", stored)


async def test_a_draft_hash_of_a_long_password_still_verifies(hasher: PasswordHasher) -> None:
    password = "пароль-" * 20
    # bcrypt 4 черновика молча отбрасывал байты после 72-го: так он и хешировал.
    draft_hash = bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt(4)).decode()

    assert await hasher.verify(password, draft_hash)


async def test_a_256_character_password_hashes_and_verifies(hasher: PasswordHasher) -> None:
    password = "ж" * 256

    assert await hasher.verify(password, await hasher.hash(password))


async def test_a_stored_value_that_is_no_bcrypt_hash_never_matches(hasher: PasswordHasher) -> None:
    # Обезличенный аккаунт черновика хранит случайный текст вместо хеша.
    assert not await hasher.verify("deleted", "deleted-3f9a0c")


async def test_a_missing_hash_checks_the_decoy_and_never_matches(hasher: PasswordHasher) -> None:
    assert not await hasher.verify("anything", None)
    assert not await hasher.verify("anything", None)


async def test_hashing_never_blocks_the_event_loop() -> None:
    pool = PasswordHasher(10, workers=1)
    ticks = 0

    async def tick() -> None:
        nonlocal ticks
        while True:
            ticks += 1
            await asyncio.sleep(0.005)

    ticker = asyncio.create_task(tick())
    try:
        await pool.hash("slow enough to notice")
    finally:
        ticker.cancel()
        pool.close()

    # Хеш стоимостью 10 занимает десятки миллисекунд; цикл за это время успевает тикать.
    assert ticks > 3

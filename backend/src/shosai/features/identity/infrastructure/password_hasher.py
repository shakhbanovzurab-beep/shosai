"""bcrypt off the event loop, in a bounded pool (§18.2; draft lesson: blocking hashing).

A hash at cost 12 takes ≈ 250 ms of CPU, so it never runs on the event loop: a pool of
half the cores (at least one) takes it, and callers wait without blocking the loop. A
sign-in for an unknown address checks a decoy hash of the same cost, so its answer takes
as long as a wrong password and does not reveal whether an account exists. A stored value
that is not a bcrypt hash (the draft's anonymised accounts hold random text) never
matches.
"""

import asyncio
import os
import secrets
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Final

import bcrypt
import structlog

from shosai.features.identity.domain.passwords import bcrypt_input

# Ложный хеш считается от случайных байтов процесса: совпасть с ним нечему.
DECOY_INPUT_BYTES: Final = 32
log = structlog.stdlib.get_logger(__name__)


class PasswordHasher:
    """Hashes and checks passwords in its own thread pool; `close` stops the pool."""

    def __init__(self, rounds: int, workers: int | None = None) -> None:
        self._rounds = rounds
        self._pool = ThreadPoolExecutor(
            max_workers=workers or max(1, (os.cpu_count() or 2) // 2),
            thread_name_prefix="password-hash",
        )
        self._decoy: bytes | None = None

    async def hash(self, password: str) -> str:
        """The bcrypt hash of the password at the configured cost."""
        hashed = await self._run(_hash, bcrypt_input(password), self._rounds)
        return hashed.decode("ascii")

    async def verify(self, password: str, stored: str | None) -> bool:
        """Whether the password matches the stored hash; a missing hash checks the decoy."""
        if stored is None:
            await self._run(_matches, bcrypt_input(password), await self._decoy_hash())
            return False
        return await self._run(_matches, bcrypt_input(password), stored.encode("ascii", "replace"))

    def close(self) -> None:
        """Stop the pool after the hashes in progress finish."""
        self._pool.shutdown(wait=True)

    async def _decoy_hash(self) -> bytes:
        if self._decoy is None:
            decoy_input = secrets.token_bytes(DECOY_INPUT_BYTES)
            self._decoy = await self._run(_hash, decoy_input, self._rounds)
        return self._decoy

    async def _run[*A, R](self, function: Callable[[*A], R], *arguments: *A) -> R:
        return await asyncio.get_running_loop().run_in_executor(self._pool, function, *arguments)


def _hash(password: bytes, rounds: int) -> bytes:
    return bcrypt.hashpw(password, bcrypt.gensalt(rounds))


def _matches(password: bytes, stored: bytes) -> bool:
    try:
        return bcrypt.checkpw(password, stored)
    except ValueError:
        # Не хеш bcrypt (обезличенный аккаунт черновика): совпасть не может.
        log.info("Сохранённый пароль не является хешем bcrypt")
        return False

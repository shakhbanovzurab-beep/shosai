"""`shosai identity admin-password-hash`: the bcrypt hash of the admin's password (ADR 0049).

The owner types the password twice without echo; the command prints only the hash, as the
`.env` line `IDENTITY_ADMIN_PASSWORD_HASH='…'`, so the password never lands in a file or a
shell history. The hash is computed at the production cost, off the event loop.
"""

import asyncio
import getpass
import sys
from collections.abc import Callable
from typing import Final, TextIO

import structlog

from shosai.features.identity.domain.admin_credentials import MIN_ADMIN_PASSWORD_LENGTH
from shosai.features.identity.domain.passwords import MAX_PASSWORD_LENGTH
from shosai.features.identity.infrastructure.password_hasher import PasswordHasher
from shosai.features.identity.settings import PRODUCTION_HASH_ROUNDS

EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
FIRST_PROMPT: Final = "Admin password: "
REPEAT_PROMPT: Final = "Repeat the password: "
log = structlog.stdlib.get_logger(__name__)

type PasswordReader = Callable[[str], str]


async def run_admin_password_hash(
    read_password: PasswordReader = getpass.getpass, out: TextIO = sys.stdout
) -> int:
    """Ask for the password twice and print its hash; return the exit code."""
    password = await asyncio.to_thread(read_password, FIRST_PROMPT)
    repeated = await asyncio.to_thread(read_password, REPEAT_PROMPT)
    if password != repeated:
        log.error("Хэш не создан: пароли не совпали")
        return EXIT_FAILED
    if not MIN_ADMIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        log.error(
            "Хэш не создан: длина пароля вне пределов",
            min_length=MIN_ADMIN_PASSWORD_LENGTH,
            max_length=MAX_PASSWORD_LENGTH,
        )
        return EXIT_FAILED
    hasher = PasswordHasher(PRODUCTION_HASH_ROUNDS, workers=1)
    try:
        hashed = await hasher.hash(password)
    finally:
        hasher.close()
    # Одинарные кавычки: Compose не примет `$2b$12$…` за подстановку переменных.
    out.write(f"IDENTITY_ADMIN_PASSWORD_HASH='{hashed}'\n")
    return EXIT_OK

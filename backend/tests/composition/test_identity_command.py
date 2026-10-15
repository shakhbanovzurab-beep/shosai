"""`shosai identity admin-password-hash`: the hash of the admin's password (ADR 0049)."""

import io
from collections.abc import Iterator

import bcrypt

from shosai.composition.identity_command import (
    EXIT_FAILED,
    EXIT_OK,
    FIRST_PROMPT,
    REPEAT_PROMPT,
    PasswordReader,
    run_admin_password_hash,
)
from shosai.entrypoints.cli import build_parser
from shosai.features.identity.domain.admin_credentials import is_bcrypt_hash

PASSWORD = "a long admin passphrase"


def typed(*answers: str) -> tuple[list[str], PasswordReader]:
    """What the owner types at each prompt, and the prompts they were asked."""
    prompts: list[str] = []
    remaining: Iterator[str] = iter(answers)

    def read(prompt: str) -> str:
        prompts.append(prompt)
        return next(remaining)

    return prompts, read


async def test_the_command_prints_only_a_quoted_hash_of_the_typed_password() -> None:
    prompts, read = typed(PASSWORD, PASSWORD)
    out = io.StringIO()

    code = await run_admin_password_hash(read, out)

    line = out.getvalue()
    assert code == EXIT_OK
    assert prompts == [FIRST_PROMPT, REPEAT_PROMPT]
    assert line.startswith("IDENTITY_ADMIN_PASSWORD_HASH='")
    assert line.endswith("'\n")
    hashed = line.removeprefix("IDENTITY_ADMIN_PASSWORD_HASH='").removesuffix("'\n")
    assert is_bcrypt_hash(hashed)
    assert hashed.startswith("$2b$12$")
    assert bcrypt.checkpw(PASSWORD.encode(), hashed.encode())
    assert PASSWORD not in line


async def test_different_or_short_passwords_print_nothing() -> None:
    for answers in ((PASSWORD, PASSWORD + "!"), ("too short", "too short")):
        _, read = typed(*answers)
        out = io.StringIO()

        code = await run_admin_password_hash(read, out)

        assert (code, out.getvalue()) == (EXIT_FAILED, "")


def test_the_command_line_names_the_tool() -> None:
    arguments = build_parser().parse_args(["identity", "admin-password-hash"])

    assert (arguments.role, arguments.tool) == ("identity", "admin-password-hash")

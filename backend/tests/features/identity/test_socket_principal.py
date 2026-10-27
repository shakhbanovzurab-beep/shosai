"""The person of a gateway socket's `hello` token, and the close code of a refused one."""

from dataclasses import dataclass
from http import HTTPStatus
from uuid import uuid4

import pytest

from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.ports.directory import PortDirectory
from shosai.core.web.sockets import Hello, SocketClose, SocketRefusedError
from shosai.features.identity.contracts import AUTHENTICATOR, Principal
from shosai.features.identity.contracts.sockets import socket_principal

PERSON = Principal(uuid4(), Home.EU, token_version=1)


@dataclass(frozen=True, slots=True)
class TokenTable:
    """An authenticator over a fixed table: a known token, an expired one and a refused one."""

    async def principal(self, bearer_token: str) -> Principal:
        """The person of the token, or identity's refusal."""
        if bearer_token == "fresh":
            return PERSON
        if bearer_token == "expired":
            raise AppError("token_expired", HTTPStatus.UNAUTHORIZED)
        raise AppError("refused", HTTPStatus.FORBIDDEN)


def ports() -> PortDirectory:
    directory = PortDirectory()
    directory.install([AUTHENTICATOR.bind(TokenTable())])
    return directory


async def test_a_fresh_token_gives_its_person() -> None:
    assert await socket_principal(ports(), Hello(1, "fresh", {})) == PERSON


@pytest.mark.parametrize(
    ("token", "code", "reason"),
    [
        ("expired", SocketClose.UNAUTHORIZED, "token_expired"),
        ("blocked", SocketClose.FORBIDDEN, "refused"),
    ],
)
async def test_a_refused_token_ends_the_socket_with_4000_plus_its_status(
    token: str, code: int, reason: str
) -> None:
    with pytest.raises(SocketRefusedError) as refused:
        await socket_principal(ports(), Hello(1, token, {}))

    assert (refused.value.code, refused.value.reason) == (code, reason)

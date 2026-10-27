"""Identity for the WS gateway's sockets (ADR 0070, LV-D3): the person of a `hello` token."""

from shosai.core.kernel.errors import AppError
from shosai.core.ports.directory import PortDirectory
from shosai.core.web.sockets import Hello, SocketRefusedError, close_code_for
from shosai.features.identity.contracts import AUTHENTICATOR, Principal


async def socket_principal(ports: PortDirectory, hello: Hello) -> Principal:
    """The person of a gateway socket's `hello` token, through identity.

    A refused token ends the socket with `4000 + status`: 4401 for an expired, invalid or
    revoked token or a person gone, 4403 when refused; the client refreshes its token and
    connects again.
    """
    try:
        return await ports.get(AUTHENTICATOR).principal(hello.token)
    except AppError as refused:
        raise SocketRefusedError(close_code_for(refused.status), refused.code) from refused

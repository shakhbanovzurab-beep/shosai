"""Who calls Leo's routes: a person by their bearer token, or the platform operator (AG-D5).

The same thread, history, turn and run routes serve both, under their own prefixes. A person's
are `/v1/agent/*`, with the person of the bearer token; the operator's are `/v1/admin/agent/*`,
behind the admin's session cookie (ADR 0049), acting as the platform operator — never a person,
so a person's token opens none of them and the admin's cookie none of a person's.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends

from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.domain.operator import OPERATOR_HOME, OPERATOR_ID
from shosai.features.identity.contracts import Principal, bearer_principal, require_admin

type Caller = Callable[..., Awaitable[Principal]]
OPERATOR_TOKEN_VERSION = 0


@dataclass(frozen=True, slots=True)
class Mount:
    """Where Leo's routes sit and who calls them."""

    prefix: str
    tags: list[str]
    caller: Caller


def person_mount(ports: PortDirectory) -> Mount:
    """A person's Leo: `/v1/agent`, by bearer token."""
    return Mount("/v1/agent", ["agent"], bearer_principal(ports))


def operator_mount(ports: PortDirectory) -> Mount:
    """The operator's Leo: `/v1/admin/agent`, by the admin's session."""
    admin = require_admin(ports)

    async def operator(_: Annotated[None, Depends(admin)]) -> Principal:
        return Principal(OPERATOR_ID, OPERATOR_HOME, OPERATOR_TOKEN_VERSION)

    return Mount("/v1/admin/agent", ["admin"], operator)

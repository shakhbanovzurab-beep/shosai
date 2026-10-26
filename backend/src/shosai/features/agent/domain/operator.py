"""The platform operator's Leo in the admin panel (ADR 0068 AG-D5; agent step 16).

The admin is not a person's account (ADR 0049): their conversations with Leo are platform data,
kept in the EU home under one fixed operator id, so the personal row-level security that keeps
every person's threads apart keeps the operator's apart too. A turn of the operator's is paid
by the platform's `admin_assistant` account, within its own ceilings, never by a plan; it is
answered in Russian, the admin panel's language; and it reads platform aggregates only: the
`platform` toolset, and of the core toolset what pages a kept result. A person's turn is never
offered `platform`, and a `platform` tool refuses any caller but the operator.
"""

from typing import Final
from uuid import UUID

from shosai.core.ai.calls import PlatformAccount
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope

OPERATOR_ID: Final = UUID("01a10000-0000-7000-8000-00000000ad31")
OPERATOR_HOME: Final = Home.EU
OPERATOR_LANGUAGE: Final = "ru"
PLATFORM_TOOLSET: Final = "platform"
# Из ядра оператору нужно только дочитать хранимый результат и подгрузить набор.
OPERATOR_CORE_TOOLS: Final = frozenset({"core.read_result", "core.load_toolset"})


def is_operator(user_id: UUID | None) -> bool:
    """Whether the caller is the platform operator."""
    return user_id == OPERATOR_ID


def operator_scope() -> TenancyScope:
    """The operator's transactions: the EU home, under the operator's id."""
    return TenancyScope(OPERATOR_HOME, OPERATOR_ID)


def payer_of(scope: TenancyScope) -> tuple[TenancyScope | None, PlatformAccount | None]:
    """Who pays a model call made for the scope: the person, or for the operator the platform."""
    if is_operator(scope.user_id):
        return None, PlatformAccount.ADMIN_ASSISTANT
    return scope, None


def offered_to(toolset: str, tool: str, *, operator: bool) -> bool:
    """Whether a tool may be offered: `platform` to the operator only, and to the operator
    nothing else but what pages a result."""
    if operator:
        return toolset == PLATFORM_TOOLSET or tool in OPERATOR_CORE_TOOLS
    return toolset != PLATFORM_TOOLSET

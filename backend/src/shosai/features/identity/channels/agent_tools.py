"""Leo's `account` toolset: how the person wants to be addressed (ADR 0029; SLICE_MAP §4.2.1).

One read tool. It reads only the account of the person the run acts for: the scope of the
tool context, never an id the model names. The plan summary joins it when billing ships.
"""

from datetime import timedelta
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from shosai.core.agent_tools.bindings import ReadTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import ToolErrorCode, ToolResult
from shosai.core.agent_tools.spec import ToolEffect, ToolSpec
from shosai.core.db.transactions import HomeTransactions
from shosai.features.identity.application.profile import Profiles


class NoArguments(BaseModel):
    """The tool takes no arguments: it always reads the signed-in person."""

    model_config = ConfigDict(extra="forbid")


class AccountProfileOutput(BaseModel):
    """How to address the person."""

    display_name: str = Field(description="The name to address the person by.")
    language: str = Field(description="The interface language code the person chose.")
    timezone: str | None = Field(description="The person's IANA time zone, if they set one.")


GET_PROFILE: Final = ToolSpec(
    name="account.get_profile",
    toolset="account",
    description=(
        "Read how the signed-in person wants to be addressed: their name, interface "
        "language and time zone. Use it before greeting them by name or scheduling in "
        "their local time."
    ),
    input=NoArguments,
    output=AccountProfileOutput,
    effect=ToolEffect.READ,
    timeout=timedelta(seconds=5),
)
ACCOUNT_TOOLS: Final = (GET_PROFILE,)


def account_tools(
    transactions: HomeTransactions, profiles: Profiles
) -> tuple[ReadTool[NoArguments, AccountProfileOutput], ...]:
    """The bound tools of the account toolset."""

    async def get_profile(
        _arguments: NoArguments, context: ToolContext
    ) -> ToolResult[AccountProfileOutput]:
        user_id = context.scope.user_id
        if user_id is None:
            return ToolResult.failed(ToolErrorCode.FORBIDDEN)
        async with transactions.begin(context.scope, read_only=True) as session:
            profile = await profiles.profile(session, user_id)
        if profile is None:
            return ToolResult.failed(ToolErrorCode.NOT_FOUND)
        return ToolResult(
            AccountProfileOutput(
                display_name=profile.display_name,
                language=profile.language,
                timezone=profile.timezone,
            )
        )

    return (ReadTool(GET_PROFILE, get_profile),)

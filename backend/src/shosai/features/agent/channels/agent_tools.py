"""Leo's own toolset, `core` (Leo §8.3; agent plan step 6): every turn offers it.

`core.read_result` pages through a tool result too long for the context, re-checking the
spaces it came from on every read (AG-D3) and naming the tool, so the turn wraps the page as it
wrapped the result; `core.load_toolset` asks for a toolset the turn did
not send, for the next round; `core.navigate` opens a page of the cabinet. The agent's turn
acts on the last two itself — the toolset joins the run, the cabinet gets `client.action` —
so their handlers only check and echo the request.
"""

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from shosai.core.agent_tools.bindings import AgentTool, ReadTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import ToolErrorCode, ToolResult
from shosai.core.agent_tools.spec import ToolEffect, ToolSpec
from shosai.features.agent.application.result_pages import ResultPages
from shosai.features.agent.domain import core_tools as tool_names
from shosai.features.agent.domain.cabinet_pages import PAGE_LIST, is_cabinet_page
from shosai.features.agent.domain.context import PATH_MAX, clean_path

TOOLSET_NAME_MAX: Final = 40
REF_MAX: Final = 64


class Strict(BaseModel):
    """Arguments the model sends: a field the schema lacks is refused."""

    model_config = ConfigDict(extra="forbid")


class ReadResultInput(Strict):
    """Which stored result, and where to continue."""

    result_ref: str = Field(
        max_length=REF_MAX, description="The result_ref a truncated tool result named."
    )
    cursor: int = Field(
        default=0,
        ge=0,
        description="0 for the first page, then the next_cursor the previous page gave.",
    )


class ReadResultOutput(BaseModel):
    """A page of a stored result."""

    text: str = Field(description="This page of the result's JSON.")
    next_cursor: int | None = Field(description="The cursor of the next page; null at the end.")
    tool: str = Field(description="The tool whose result this is.")


class LoadToolsetInput(Strict):
    """The toolset to load."""

    name: str = Field(
        max_length=TOOLSET_NAME_MAX,
        description="One of the toolsets this tool's description lists as available.",
    )


class LoadToolsetOutput(BaseModel):
    """The toolset that joins the next round."""

    loaded: str = Field(description="The toolset whose tools you can call from the next round.")


class NavigateInput(Strict):
    """The page to open."""

    to: str = Field(
        max_length=PATH_MAX,
        description=(
            "A page of the Shosai web app with its ids filled in, such as /app/kanban for "
            "boards and every task, /app/notes for meetings' notes or /app/file-manager."
        ),
    )


class NavigateOutput(BaseModel):
    """The page the user's screen opens."""

    to: str = Field(description="The path the web app opens.")


READ_RESULT: Final = ToolSpec(
    name=tool_names.READ_RESULT,
    toolset="core",
    description=(
        "Read more of a tool result that was cut to fit: call it with the result_ref the "
        "truncated result named, then with each next_cursor until it is null."
    ),
    input=ReadResultInput,
    output=ReadResultOutput,
    effect=ToolEffect.READ,
    result_budget=3_000,
)
LOAD_TOOLSET: Final = ToolSpec(
    name=tool_names.LOAD_TOOLSET,
    toolset="core",
    description=(
        "Load another toolset of the user's Shosai when none of your tools fits the request. "
        "Its tools become available from your next round."
    ),
    input=LoadToolsetInput,
    output=LoadToolsetOutput,
    effect=ToolEffect.READ,
    result_budget=200,
    step_detail="name",
)
NAVIGATE: Final = ToolSpec(
    name=tool_names.NAVIGATE,
    toolset="core",
    description=(
        "Open a page of the Shosai web app on the user's screen, when they ask to go there."
    ),
    input=NavigateInput,
    output=NavigateOutput,
    effect=ToolEffect.CLIENT,
    result_budget=200,
    step_detail="to",
)
CORE_TOOLS: Final = (READ_RESULT, LOAD_TOOLSET, NAVIGATE)


def core_tools(pages: ResultPages) -> tuple[AgentTool, ...]:
    """The core toolset bound to its handlers."""

    async def read_result(
        arguments: ReadResultInput, context: ToolContext
    ) -> ToolResult[ReadResultOutput]:
        page = await pages.page(context, arguments.result_ref, arguments.cursor)
        if isinstance(page, ToolErrorCode):
            return ToolResult.failed(page)
        return ToolResult(
            ReadResultOutput(text=page.text, next_cursor=page.next_cursor, tool=page.tool)
        )

    async def load_toolset(
        arguments: LoadToolsetInput, context: ToolContext
    ) -> ToolResult[LoadToolsetOutput]:
        del context
        return ToolResult(LoadToolsetOutput(loaded=arguments.name))

    async def navigate(
        arguments: NavigateInput, context: ToolContext
    ) -> ToolResult[NavigateOutput]:
        del context
        path = clean_path(arguments.to)
        if path is None:
            return ToolResult.failed(ToolErrorCode.INVALID_ARGUMENTS, fields="to")
        if not is_cabinet_page(path):
            # Выдуманную страницу кабинет открыл бы как «не найдено»: модель выбирает из списка.
            return ToolResult.failed(ToolErrorCode.NOT_FOUND, fields="to", pages=PAGE_LIST)
        return ToolResult(NavigateOutput(to=path))

    return (
        ReadTool(READ_RESULT, read_result),
        ReadTool(LOAD_TOOLSET, load_toolset),
        ReadTool(NAVIGATE, navigate),
    )

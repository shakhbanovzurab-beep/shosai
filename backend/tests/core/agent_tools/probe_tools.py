"""A read and a write tool of a probe slice, as a slice would declare and bind them."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from shosai.core.agent_tools.bindings import ReadTool, WriteTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import (
    PlannedEffect,
    Preview,
    ToolError,
    ToolErrorCode,
    ToolResult,
)
from shosai.core.agent_tools.spec import Reversibility, ToolEffect, ToolSpec
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope

USER_ID = UUID("0190f0f0-0000-7000-8000-0000000000d1")


class SearchNotes(BaseModel):
    """Arguments of the probe search."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=200, description="Words to look for.")
    limit: int = Field(default=5, ge=1, le=20, description="How many notes to return.")


class FoundNotes(BaseModel):
    """What the probe search found."""

    titles: list[str]


class ArchiveNotes(BaseModel):
    """Arguments of the probe archive."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, description="Which notes to archive.")


class Archived(BaseModel):
    """How many notes the probe archive changed."""

    archived: int


SEARCH = ToolSpec(
    name="notes.search",
    toolset="notes",
    description="Find the user's notes by words in their title or text.",
    input=SearchNotes,
    output=FoundNotes,
    effect=ToolEffect.READ,
)
ARCHIVE = ToolSpec(
    name="notes.archive",
    toolset="notes",
    description="Archive the user's notes that match a query.",
    input=ArchiveNotes,
    output=Archived,
    effect=ToolEffect.WRITE,
    reversibility=Reversibility.REVERSIBLE,
    invalidates=("notes",),
)


def context() -> ToolContext:
    """A call for the probe user in the EU home, due in a minute."""
    return ToolContext(
        scope=TenancyScope(Home.EU, USER_ID),
        run_id=UUID(int=7),
        deadline=datetime.now(UTC) + timedelta(minutes=1),
    )


async def search(args: SearchNotes, _context: ToolContext) -> ToolResult[FoundNotes]:
    """The probe search: one title per word."""
    return ToolResult(FoundNotes(titles=args.query.split()[: args.limit]))


async def plan_archive(args: ArchiveNotes, _context: ToolContext) -> PlannedEffect | ToolError:
    """Freeze the notes the query matches; none matched is an error, not an empty write."""
    if args.query == "nothing":
        return ToolError(ToolErrorCode.NOT_FOUND)
    return PlannedEffect(targets=("note-1", "note-2"), data={"query": args.query})


async def preview_archive(planned: PlannedEffect, _context: ToolContext) -> Preview:
    """The server's account of the plan."""
    return Preview("agent.notes.archive", {"count": len(planned.targets)})


async def execute_archive(
    planned: PlannedEffect, _context: ToolContext, _idempotency_key: str
) -> ToolResult[Archived]:
    """Apply the plan to its targets only."""
    return ToolResult(Archived(archived=len(planned.targets)))


SEARCH_TOOL = ReadTool(SEARCH, search)
ARCHIVE_TOOL = WriteTool(ARCHIVE, plan_archive, preview_archive, execute_archive)

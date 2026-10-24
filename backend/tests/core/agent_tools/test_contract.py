"""The tool contract: malformed specs stop at declaration, arguments are validated, not guessed."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel

from shosai.core.agent_tools.arguments import parse_arguments
from shosai.core.agent_tools.bindings import ReadTool, WriteTool
from shosai.core.agent_tools.catalog import AgentToolCatalog
from shosai.core.agent_tools.context import Taint, ToolContext
from shosai.core.agent_tools.provenance import Provenance
from shosai.core.agent_tools.results import (
    TOOL_ERROR_TEXTS,
    PlannedEffect,
    ToolError,
    ToolErrorCode,
    ToolResult,
)
from shosai.core.agent_tools.spec import CostClass, Reversibility, ToolEffect
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from tests.core.agent_tools.probe_tools import (
    ARCHIVE,
    ARCHIVE_TOOL,
    SEARCH,
    SEARCH_TOOL,
    SearchNotes,
    context,
    search,
)


class LooseInput(BaseModel):
    """An input model that accepts fields it does not declare."""

    query: str


@pytest.mark.parametrize(
    "changes",
    [
        {"name": "search"},
        {"name": "Notes.Search"},
        {"name": "notes." + "x" * 60},
        {"toolset": "Notes"},
        {"description": " "},
        {"description": "x" * 1025},
        {"result_budget": 0},
        {"timeout": timedelta(0)},
        {"timeout": timedelta(minutes=3)},
        {"entitlement": "Plan Pro"},
        {"reversibility": Reversibility.REVERSIBLE},
        {"effect": ToolEffect.EGRESS},
        {"invalidates": ("notes",)},
        {"input": LooseInput},
    ],
)
def test_a_malformed_spec_is_refused_when_declared(changes: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="инструмент"):
        replace(SEARCH, **changes)


def test_a_write_names_its_reversibility_and_egress_is_metered() -> None:
    with pytest.raises(ValueError, match="обратимость"):
        replace(ARCHIVE, reversibility=None)

    web = replace(SEARCH, name="web.search", effect=ToolEffect.EGRESS, cost_class=CostClass.METERED)

    assert web.effect is ToolEffect.EGRESS


def test_the_input_schema_is_the_model_s_json_schema() -> None:
    schema = SEARCH.input_schema()

    assert schema["additionalProperties"] is False
    assert schema["required"] == ["query"]


@pytest.mark.parametrize(
    ("raw", "fields"),
    [
        ('{"query": ""}', "query"),
        ('{"query": "plan", "limit": 50}', "limit"),
        ('{"query": "plan", "folder": "x"}', "folder"),
        ('{"query": "pl', "(arguments)"),
        ("[]", "(arguments)"),
        ({"limit": "many"}, "query, limit"),
    ],
)
def test_arguments_that_do_not_fit_are_an_error_naming_the_fields(
    raw: str | dict[str, object], fields: str
) -> None:
    parsed = parse_arguments(SEARCH, raw)

    assert parsed == ToolError(ToolErrorCode.INVALID_ARGUMENTS, {"fields": fields})
    assert isinstance(parsed, ToolError)
    assert "secret" not in str(parsed.params)


def test_valid_arguments_become_the_input_model() -> None:
    assert parse_arguments(SEARCH, '{"query": "plan"}') == SearchNotes(query="plan", limit=5)


async def test_a_write_is_planned_previewed_and_executed_on_the_plan_only() -> None:
    ctx = context()
    args = parse_arguments(ARCHIVE, {"query": "old"})
    assert not isinstance(args, ToolError)

    planned = await ARCHIVE_TOOL.plan(args, ctx)
    assert isinstance(planned, PlannedEffect)
    preview = await ARCHIVE_TOOL.preview(planned, ctx)
    result = await ARCHIVE_TOOL.execute(planned, ctx, f"{UUID(int=9)}:0")

    assert preview.params == {"count": 2}
    assert result.output is not None
    assert result.output.archived == 2
    assert await ARCHIVE_TOOL.plan(type(args)(query="nothing"), ctx) == ToolError(
        ToolErrorCode.NOT_FOUND
    )


def test_a_result_is_output_or_error_and_an_error_reads_its_registered_text() -> None:
    failed: ToolResult[BaseModel] = ToolResult.failed(ToolErrorCode.TIMEOUT)

    assert failed.error is not None
    assert failed.error.text == TOOL_ERROR_TEXTS[ToolErrorCode.TIMEOUT]
    assert set(TOOL_ERROR_TEXTS) == set(ToolErrorCode)
    with pytest.raises(ValueError, match="либо данные"):
        ToolResult()


def test_a_read_and_a_write_bind_only_to_their_kind_of_spec() -> None:
    with pytest.raises(ValueError, match="WriteTool"):
        ReadTool(ARCHIVE, search)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="только для записи"):
        WriteTool(SEARCH, *(lambda *_: None,) * 3)  # type: ignore[arg-type]


def test_a_call_acts_for_a_person_until_an_aware_deadline() -> None:
    deadline = datetime.now(UTC) + timedelta(seconds=30)

    with pytest.raises(ValueError, match="от имени человека"):
        ToolContext(TenancyScope(Home.EU), UUID(int=1), deadline)
    with pytest.raises(ValueError, match="часовым поясом"):
        ToolContext(context().scope, UUID(int=1), deadline.replace(tzinfo=None))
    assert 0 < context().remaining_seconds() <= 60
    assert Taint.SUSPICIOUS > Taint.EXTERNAL > Taint.NONE


def test_the_catalog_holds_each_name_once_and_answers_by_toolset() -> None:
    catalog = AgentToolCatalog()
    with pytest.raises(RuntimeError, match="до установки"):
        catalog.tool("notes.search")

    catalog.install([SEARCH_TOOL, ARCHIVE_TOOL])

    assert catalog.tool("notes.search") is SEARCH_TOOL
    assert catalog.tool("notes.delete_everything") is None
    assert catalog.toolset("notes") == (SEARCH_TOOL, ARCHIVE_TOOL)
    assert catalog.toolsets() == ("notes",)
    with pytest.raises(RuntimeError, match="уже установлены"):
        catalog.install([])
    with pytest.raises(ValueError, match="дважды"):
        AgentToolCatalog().install([SEARCH_TOOL, SEARCH_TOOL])


def test_a_result_s_untrusted_text_is_labelled_from_the_closed_set() -> None:
    labelled = replace(SEARCH, provenance=Provenance.MEETING_SPEECH)

    assert SEARCH.provenance is None
    assert labelled.provenance == "meeting:speech"
    assert {label.value for label in Provenance} == {
        "mail", "web", "file:foreign", "file:own", "meeting:speech", "task:foreign", "memory",
        "skill:user",
    }  # fmt: skip

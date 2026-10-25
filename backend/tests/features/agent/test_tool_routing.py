"""Which tools a turn offers: loaded, sticky, switched off, by page and plan (step 6, AG-D7)."""

import re
import uuid
from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime
from typing import Final

from pydantic import JsonValue

from shosai.composition.features import FEATURES
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.agent.application.surface_digest import SubjectKind
from shosai.features.agent.application.tool_offer import surface_toolsets
from shosai.features.agent.application.tool_registry import (
    OFFERED_EFFECTS,
    TOOLS_PER_TOOLSET,
    Gates,
    wire_name,
)
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.domain.budgets import SEGMENT_CAPS, Segment, estimate_tokens
from shosai.features.agent.domain.digests import compact
from shosai.features.agent.domain.preferences import ResponseLength
from shosai.features.agent.domain.routing import CORE, RouteFacts, ToolsetFacts, route
from shosai.features.agent.infrastructure.person_records import AgentSettingsRecord
from shosai.features.agent.infrastructure.prompts import LOADABLE
from tests.features.agent.test_thread_care import sample
from tests.features.agent.tool_doubles import FILES_SEARCH, NOTES_SEARCH, calling, saying
from tests.features.agent.turn_bench import HOME, TurnBench

LOADABLE_TEXT: Final = LOADABLE.removesuffix("{names}.")

# Имена функций у провайдеров: латиница, цифры, «_» и «-», до 64 символов.
PROVIDER_NAME: Final = re.compile(r"[a-zA-Z0-9_-]{1,64}")


def offered(turn_bench: TurnBench, call: int) -> set[str]:
    """The wire names a model call was offered."""
    return {tool.name for tool in turn_bench.model.calls[call].tools}


async def test_a_toolset_routing_left_out_is_loaded_for_the_next_round_and_sticks(
    turn_bench: TurnBench,
) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    turn_bench.model.scripts = [
        calling(("core__load_toolset", '{"name": "archive"}')),
        calling(("archive__search", "{}")),
        saying("Archived."),
    ]
    registry, _ = turn_bench.observed

    await turn_bench.ask(person, thread, "Search the archive.")
    before, after = offered(turn_bench, 0), offered(turn_bench, 1)
    load = next(t for t in turn_bench.model.calls[0].tools if t.name == "core__load_toolset")
    turn_bench.model.calls.clear()
    turn_bench.model.scripts = [saying("Again.")]
    await turn_bench.ask(person, thread, "And now?")

    assert ("archive__search" in before, "archive__search" in after) == (False, True)
    assert turn_bench.tools.ran == ["archive"]
    assert load.description.endswith(f"{LOADABLE_TEXT}archive.")
    assert sample(registry, "shosai_agent_load_toolset_total") == 1
    # Липкий архив занял место сегмента: теперь остальные наборы только названы.
    again = next(t for t in turn_bench.model.calls[0].tools if t.name == "core__load_toolset")
    assert "archive__search" in offered(turn_bench, 0)
    assert again.description.endswith(f"{LOADABLE_TEXT}notes, tasks, files.")


async def test_a_switched_off_tool_is_never_offered_and_a_write_is(turn_bench: TurnBench) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    async with turn_bench.homes.transactions.begin(TenancyScope(HOME, person)) as session:
        session.add(AgentSettingsRecord(user_id=person, knowledge_base_search=False))
    turn_bench.model.scripts = [calling(("files__search", '{"query": "x"}')), saying("No.")]

    await turn_bench.ask(person, thread, "Search my files.")

    assert "files__search" not in offered(turn_bench, 0)
    assert "tasks__create" in offered(turn_bench, 0)
    assert "notes__search" in offered(turn_bench, 0)
    assert turn_bench.tools.ran == []


def payload(path: str | None, subject: SubjectKind | None = None) -> TurnPayload:
    """A turn asked on a page."""
    return TurnPayload(
        home=HOME, user_id=uuid.uuid4(), run_id=uuid.uuid4(), thread_id=uuid.uuid4(),
        started_at=datetime.now(UTC), question_id=uuid.uuid4(), reply_id=uuid.uuid4(),
        language="en", length=ResponseLength.BALANCED, cross_border_consent=False,
        token_route="within_allowance", path=path, subject_kind=subject,
        subject_id=uuid.uuid4() if subject else None,
    )  # fmt: skip


def test_reads_of_every_toolset_come_before_the_writes_of_any() -> None:
    toolsets = (
        ToolsetFacts(CORE, 500),
        ToolsetFacts("notes", 2_200, read_tokens=1_000),
        ToolsetFacts("tasks", 2_900, read_tokens=1_000),
        ToolsetFacts("files", 1_000, read_tokens=400),
        ToolsetFacts("account", 450),
    )

    plain = route(RouteFacts(toolsets))
    on_board = route(RouteFacts(toolsets, surface=frozenset({"tasks"})))

    assert (plain.selected, plain.reading) == (("core", "files", "account"), ("notes", "tasks"))
    assert plain.deferred == ("notes", "tasks")
    assert (on_board.selected, on_board.reading) == (("core", "tasks"), ("files",))
    assert on_board.deferred == ("notes", "files", "account")


def test_a_page_brings_the_toolsets_of_its_section_and_its_subject() -> None:
    assert surface_toolsets(payload("/app/kanban")) == {"tasks"}
    assert surface_toolsets(payload("/app/meetings/42", SubjectKind.FILE)) == {"notes", "files"}
    assert surface_toolsets(payload("/app/billing?tab=plans")) == {"account"}
    assert surface_toolsets(payload("/app/dashboard")) == frozenset()
    assert surface_toolsets(payload("https://example.com/app/notes")) == frozenset()
    assert surface_toolsets(payload(None, SubjectKind.BOARD)) == {"tasks"}


def test_gates_admit_a_tool_by_its_switch_and_its_plan() -> None:
    entitled = replace(NOTES_SEARCH, entitlement="shared_workspace")
    on = Gates(frozenset({"agent.knowledge_base_search"}))

    assert on.admit(FILES_SEARCH)
    assert not Gates(frozenset()).admit(FILES_SEARCH)
    assert not on.admit(entitled)
    assert not Gates(frozenset(), frozenset()).admit(entitled)
    assert Gates(frozenset(), frozenset({"shared_workspace"})).admit(entitled)


def test_every_slice_s_toolset_fits_the_registry_and_the_wire() -> None:
    specs = [spec for feature in FEATURES for spec in feature.agent_tools]
    per_toolset = Counter(spec.toolset for spec in specs)
    wire = [wire_name(spec.name) for spec in specs]
    offered_tokens: Counter[str] = Counter()
    for spec in specs:
        if spec.effect in OFFERED_EFFECTS:
            schema: dict[str, JsonValue] = {
                "name": wire_name(spec.name),
                "description": spec.description,
                "parameters": spec.input_schema(),
            }
            offered_tokens[spec.toolset] += estimate_tokens(compact(schema))

    assert {"core", "notes", "tasks", "files", "account"} <= set(per_toolset)
    assert max(per_toolset.values()) <= TOOLS_PER_TOOLSET
    assert len(set(wire)) == len(wire)
    assert all(PROVIDER_NAME.fullmatch(name) for name in wire)
    assert max(offered_tokens.values()) <= SEGMENT_CAPS[Segment.TOOLS]

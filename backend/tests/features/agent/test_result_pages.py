"""Kept results and their digests: what is paged back, and to whom (step 6, AG-D3)."""

import json
import uuid
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st
from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import ToolErrorCode
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.result_pages import PAGE_BYTES, ResultPage, ResultPages
from shosai.features.agent.domain.digests import compact, digest, fits
from shosai.features.workspaces.contracts import (
    MEMBERSHIP_READER,
    ActiveMembership,
    WorkspaceRole,
)
from tests.features.agent.turn_bench import HOME
from tests.harness.database_access import DatabaseAccess

LEAVES = st.one_of(st.text(max_size=300), st.integers(), st.booleans(), st.none())
RESULTS = st.dictionaries(
    st.sampled_from(["items", "title", "notes", "total"]),
    st.one_of(LEAVES, st.lists(st.one_of(LEAVES, st.dictionaries(st.just("text"), LEAVES)))),
)


@given(RESULTS, st.integers(min_value=30, max_value=600))
def test_a_digest_is_valid_json_within_its_budget_that_names_each_cut_list(
    result: dict[str, JsonValue], budget: int
) -> None:
    cut = digest(result, budget)

    if fits(result, budget):
        assert cut is not None
        assert cut.value == result
        assert cut.omitted == {}
    if cut is not None:
        assert fits(cut.value, budget)
        assert json.loads(compact(cut.value)) == cut.value
        assert all(total >= 2 for total in cut.omitted.values())


@dataclass
class Memberships:
    """The workspaces each person is in now."""

    spaces: dict[uuid.UUID, set[uuid.UUID]] = field(default_factory=dict)

    async def active(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> tuple[ActiveMembership, ...]:
        """The person's workspaces."""
        del session
        return tuple(
            ActiveMembership(org, uuid.uuid4(), WorkspaceRole.MEMBER)
            for org in self.spaces.get(user_id, set())
        )

    async def has_memberships(self, session: AsyncSession, user_id: uuid.UUID) -> bool:
        """Whether the person is in a workspace."""
        return bool(await self.active(session, user_id))

    async def members(
        self, session: AsyncSession, org_id: uuid.UUID, user_ids: Collection[uuid.UUID]
    ) -> Mapping[uuid.UUID, ActiveMembership]:
        """No member is asked for here."""
        del session, org_id, user_ids
        return {}


def pages_of(homes: DatabaseAccess, memberships: Memberships, now: datetime) -> ResultPages:
    """Kept results over the slot's homes, at a moment."""
    ports = PortDirectory()
    ports.install([MEMBERSHIP_READER.bind(memberships)])
    return ResultPages(homes.transactions, ports, lambda: now)


def as_person(person: uuid.UUID) -> ToolContext:
    """A call of a person's run."""
    deadline = datetime.now(UTC) + timedelta(minutes=1)
    return ToolContext(TenancyScope(HOME, person), uuid.uuid4(), deadline)


async def read_all(pages: ResultPages, context: ToolContext, ref: str) -> list[ResultPage]:
    """Every page of a kept result."""
    found: list[ResultPage] = []
    cursor: int | None = 0
    while cursor is not None:
        page = await pages.page(context, ref, cursor)
        assert isinstance(page, ResultPage)
        found.append(page)
        cursor = page.next_cursor
    return found


async def test_a_kept_result_is_paged_whole_to_its_person_and_to_no_one_else(
    homes: DatabaseAccess,
) -> None:
    person, stranger, workspace = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)
    memberships = Memberships({person: {workspace}})
    pages = pages_of(homes, memberships, now)
    whole = json.dumps({"items": ["встреча о бюджете — решено"] * 400}, ensure_ascii=False)

    ref = str(await pages.keep(as_person(person), "notes.search", whole, frozenset({workspace})))
    read = await read_all(pages, as_person(person), ref)
    stranger_reads = await pages.page(as_person(stranger), ref, 0)
    later = await pages_of(homes, memberships, now + timedelta(days=31)).page(
        as_person(person), ref, 0
    )
    memberships.spaces[person] = set()
    after_leaving = await pages.page(as_person(person), ref, 0)

    assert "".join(page.text for page in read) == whole
    assert len(read) > 1
    assert all(len(page.text.encode()) <= PAGE_BYTES for page in read)
    assert {page.tool for page in read} == {"notes.search"}
    assert stranger_reads is ToolErrorCode.NOT_FOUND
    assert later is ToolErrorCode.NOT_FOUND
    assert after_leaving is ToolErrorCode.FORBIDDEN
    assert await pages.page(as_person(person), "not-a-ref", 0) is ToolErrorCode.NOT_FOUND


async def test_a_result_naming_no_sources_is_kept_as_from_every_workspace_of_its_person(
    homes: DatabaseAccess,
) -> None:
    person, first, second = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    memberships = Memberships({person: {first, second}})
    pages = pages_of(homes, memberships, datetime.now(UTC))

    ref = str(await pages.keep(as_person(person), "account.get_plan", "{}", None))
    readable = await pages.page(as_person(person), ref, 0)
    memberships.spaces[person] = {first}
    after_leaving_one = await pages.page(as_person(person), ref, 0)

    assert isinstance(readable, ResultPage)
    assert after_leaving_one is ToolErrorCode.FORBIDDEN

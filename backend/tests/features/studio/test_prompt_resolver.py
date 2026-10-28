"""A person's prompts for their consumers (studio step 10, plan §3.4): the active prompt with
its installed skills in order, a skill uninstalled since absent, the skills past the budget
left out and counted, the built-in prompt when none is active, and the personal context."""

import pytest
from sqlalchemy import delete

from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.agent.infrastructure.person_records import AgentSkillRecord
from shosai.features.studio.contracts import RolePrompt, RoutePerson
from shosai.features.studio.domain.roles import PromptRole
from shosai.features.studio.infrastructure.person_records import ContextRecord
from shosai.features.studio.infrastructure.route_metrics import SKILLS_LEFT_OUT
from tests.features.studio.catalogue_bench import catalogue_bench, person
from tests.features.studio.resolution_kit import Resolution, active_prompt, resolution
from tests.harness.database_access import DatabaseAccess


@pytest.fixture
async def bench(homes: DatabaseAccess) -> Resolution:
    """The resolver over the slot's homes."""
    return await resolution(catalogue_bench(homes))


async def prompt_of(bench: Resolution, who: RoutePerson, role: PromptRole) -> RolePrompt:
    """The role's prompt in the person's transaction."""
    async with bench.catalogue.homes.transactions.begin(
        TenancyScope(who.home, who.user_id)
    ) as session:
        return await bench.resolver.role_prompt(session, who.user_id, role)


async def test_the_active_prompt_comes_with_its_skills_in_order(bench: Resolution) -> None:
    who = person()
    skills = await active_prompt(
        bench.catalogue,
        who,
        "Explain the complexity.",
        [("pdf", "Read PDFs."), ("sql", "Write SQL.")],
    )

    found = await prompt_of(bench, who, PromptRole.CODE)
    other = await prompt_of(bench, who, PromptRole.NOTES)

    assert found.body == "Explain the complexity."
    assert [(skill.skill_id, skill.name, skill.body) for skill in found.skills] == [
        (skills[0], "pdf", "Read PDFs."), (skills[1], "sql", "Write SQL."),
    ]  # fmt: skip
    assert other == RolePrompt(None)


async def test_an_uninstalled_skill_is_absent_and_the_budget_leaves_the_rest_out(
    bench: Resolution,
) -> None:
    who = person()
    gone, *_ = await active_prompt(
        bench.catalogue, who, "x" * 9_000,
        [("gone", "Old."), ("big", "y" * 24_000), ("late", "z" * 3_000)],
    )  # fmt: skip
    async with bench.catalogue.homes.transactions.begin(
        TenancyScope(who.home, who.user_id)
    ) as session:
        await session.execute(delete(AgentSkillRecord).where(AgentSkillRecord.id == gone))

    found = await prompt_of(bench, who, PromptRole.CODE)

    # 3 000 токенов указаний и 8 024 навыка «big» — в бюджете 12 000; «late» (1 024) уже не входит.
    assert [skill.name for skill in found.skills] == ["big"]
    assert bench.counted(SKILLS_LEFT_OUT) == 1


async def test_the_personal_context_is_the_person_s_own_words(bench: Resolution) -> None:
    who, stranger = person(), person()
    scope = TenancyScope(who.home, who.user_id)
    async with bench.catalogue.homes.transactions.begin(scope) as session:
        session.add(ContextRecord(user_id=who.user_id, content="I lead a design team."))

    async with bench.catalogue.homes.transactions.begin(scope) as session:
        mine = await bench.resolver.personal_context(session, who.user_id)
    async with bench.catalogue.homes.transactions.begin(
        TenancyScope(stranger.home, stranger.user_id)
    ) as session:
        none = await bench.resolver.personal_context(session, stranger.user_id)

    assert (mine, none) == ("I lead a design team.", "")

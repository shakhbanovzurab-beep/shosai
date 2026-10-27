"""The agent's `FrictionJudge` over the engine: a stronger card only from an active version,
each card's end kept by its subject (decisions step 5; ADR 0069 DL-D4)."""

import uuid

from shosai.core.agent_tools.context import Taint
from shosai.core.agent_tools.spec import Reversibility
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.agent.contracts import CardEnd, Friction, FrictionFacts
from shosai.features.decisions.channels.agent_ports import AgentFrictionJudge
from shosai.features.decisions.domain.policies.action_friction import ACTION_FRICTION
from tests.features.decisions.engine_bench import FRICTION_CUTS, bench, matching, stored

ACTIVE = stored(ACTION_FRICTION, "active", FRICTION_CUTS)
SHADOW = stored(ACTION_FRICTION, "shadow", FRICTION_CUTS)


def facts(rule: Friction = Friction.STANDARD) -> FrictionFacts:
    """A card for one person's two tasks, as the agent sends it."""
    return FrictionFacts(
        tool="tasks.create", toolset="tasks", reversibility=Reversibility.REVERSIBLE,
        taint=Taint.NONE, rule=rule, question="Создай две задачи на завтра",
        card="Создать задачи\nЗадачи: 2", items=2, other_space=False, rounds=1, language="ru",
        scope=TenancyScope(Home.EU, uuid.uuid4()), cross_border_consent=True,
        action_id=uuid.uuid4(),
    )  # fmt: skip


async def test_an_active_version_that_finds_the_change_wide_warns() -> None:
    test = bench(ACTIVE)
    test.jev.answers = matching(narrow=False)
    card = facts()

    judged = await AgentFrictionJudge(test.engine).judge(card)

    assert judged is Friction.WARNING
    [(home, row)] = test.rows.decisions
    assert (home, row["subject_kind"], row["subject_id"]) == (Home.EU, "action", card.action_id)
    [(_, request)] = test.jev.asked
    assert "Создай две задачи на завтра" in str(request.state)


async def test_a_narrow_match_or_a_shadow_version_adds_nothing() -> None:
    narrow, shadow = bench(ACTIVE), bench(SHADOW)
    narrow.jev.answers = matching(narrow=True)
    shadow.jev.answers = matching(narrow=False)

    judged = [await AgentFrictionJudge(test.engine).judge(facts()) for test in (narrow, shadow)]
    await shadow.engine.drain()

    assert judged == [None, None]
    assert [len(test.rows.decisions) for test in (narrow, shadow)] == [1, 1]


async def test_a_card_the_rule_already_warns_is_never_asked() -> None:
    test = bench(ACTIVE)

    judged = await AgentFrictionJudge(test.engine).judge(facts(Friction.WARNING))

    assert judged is None
    assert (test.jev.asked, test.rows.decisions) == ([], [])


async def test_a_card_s_end_is_kept_by_its_subject_in_the_person_s_home() -> None:
    test = bench(ACTIVE)
    action_id = uuid.uuid4()

    AgentFrictionJudge(test.engine).ended(Home.RU, action_id, CardEnd.EXPIRED)

    [(home, row)] = test.rows.outcomes
    assert (home, row["point"], row["subject_kind"], row["subject_id"]) == (
        Home.RU, "action.friction", "action", action_id,
    )  # fmt: skip
    assert row["observation"] == {"resolution": "expired"}

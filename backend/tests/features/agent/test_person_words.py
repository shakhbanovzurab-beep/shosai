"""The person's own words of a turn, for memory's admission (memory step 5, ADR 0071)."""

import uuid

from shosai.core.agent_tools.context import Taint
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.agent.application.person_words import AgentPersonWords
from tests.features.agent.turn_bench import HOME, TurnBench, stream_of


async def test_a_turn_gives_its_question_and_the_exchange_before_it(
    turn_bench: TurnBench,
) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    await turn_bench.ask(person, thread, "I moved to Berlin last week")
    events = stream_of(await turn_bench.ask(person, thread, "Remember that I'm vegetarian"))
    run_id = uuid.UUID(str(events[0][2]["run_id"]))

    scope = TenancyScope(HOME, person)
    async with turn_bench.homes.transactions.begin(scope, read_only=True) as session:
        words = await AgentPersonWords().of_turn(session, person, run_id)
        stranger = await AgentPersonWords().of_turn(session, uuid.uuid4(), run_id)
        unknown = await AgentPersonWords().of_turn(session, person, uuid.uuid4())

    assert words is not None
    assert words.text == "Remember that I'm vegetarian"
    assert words.thread_id == uuid.UUID(thread)
    assert words.org_id is None
    assert words.taint is Taint.NONE
    assert [exchange.question for exchange in words.before] == ["I moved to Berlin last week"]
    assert words.before[0].answer_head
    assert stranger is None
    assert unknown is None

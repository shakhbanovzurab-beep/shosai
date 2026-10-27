"""Leo's voice conversations over the agent (LEO-voice step 4, ADR 0070 LV-D4…LV-D6).

A conversation opens on the person's thread after a text turn's checks; the voice model's tool
calls run through the agent's round — a read answers it with its sources noted, a write
becomes a card and never runs — and every exchange lands in the thread as a run of channel
`voice` with the person's phrase and Leo's answer.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from prometheus_client import CollectorRegistry

from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.agent.application.threads import Threads
from shosai.features.agent.application.voice_turns import AgentVoiceTurns, VoiceParts
from shosai.features.agent.contracts.voice import VoiceExchange, VoiceStart
from shosai.features.agent.infrastructure.person_records import AgentSettingsRecord
from shosai.features.identity.contracts import Principal
from tests.features.agent.turn_bench import HOME, TurnBench
from tests.harness.connections import fetch_rows

PLAIN = VoiceStart(workspace_id=None, thread_id=None, path=None, locale="en")
RUNS = "SELECT channel, status, tool_calls FROM agent_runs WHERE thread_id = %s"
MESSAGES = (
    "SELECT role, status, text, action_ids FROM agent_messages WHERE thread_id = %s "
    "ORDER BY created_at"
)


class Heard:
    """What a call told the conversation's socket."""

    def __init__(self) -> None:
        self.steps: list[tuple[str, str]] = []
        self.cards: list[uuid.UUID] = []

    async def step(self, activity: str, status: str) -> None:
        """A step and its status."""
        self.steps.append((activity, status))

    async def proposed(self, action_id: uuid.UUID) -> None:
        """A card."""
        self.cards.append(action_id)


def voices(bench: TurnBench) -> AgentVoiceTurns:
    """The agent's voice turns over the bench's parts."""
    transactions, ports = bench.homes.transactions, bench.ports
    threads = Threads(transactions, (ports, EffectLedger(EffectKeyMetrics(CollectorRegistry()))))
    parts = bench.parts
    return AgentVoiceTurns(
        VoiceParts(transactions, ports, threads, parts.routing, parts.tools, parts.outbox)
    )


def exchange(question: str, answer: str, *, interrupted: bool = False) -> VoiceExchange:
    """An exchange that took two seconds."""
    ended = datetime.now(UTC)
    return VoiceExchange(question, answer, ended - timedelta(seconds=2), ended, interrupted)


async def test_a_read_answers_the_voice_model_and_the_exchange_lands_in_a_new_thread(
    turn_bench: TurnBench,
) -> None:
    person = uuid.uuid4()
    talk = await voices(turn_bench).open(Principal(person, HOME, 0), PLAIN)
    heard = Heard()

    answer = await talk.call("c-1", "notes__search", '{"query": "budget"}', heard)
    await talk.record(exchange("What about the budget?", "Travel was cut by a fifth."))

    names = {tool.name for tool in talk.tools}
    # Догрузить набор голос не может: и большой `archive` приходит сразу, целиком.
    assert {"notes__search", "tasks__create", "archive__search"} <= names
    assert not names & {"core__load_toolset", "core__navigate"}
    assert "Budget review" in json.loads(answer)["result"]
    assert "Speak in the language the person speaks" in talk.instruction
    assert talk.cross_border_consent is False
    assert turn_bench.tools.ran == ["budget"]
    assert heard.steps == [("notes.search", "running"), ("notes.search", "done")]
    rows = await fetch_rows(turn_bench.connection, RUNS, (talk.thread_id,))
    assert [(r["channel"], r["status"], r["tool_calls"]) for r in rows] == [
        ("voice", "completed", 1)
    ]
    messages = await fetch_rows(turn_bench.connection, MESSAGES, (talk.thread_id,))
    assert [(m["role"], m["text"]) for m in messages] == [
        ("user", "What about the budget?"),
        ("assistant", "Travel was cut by a fifth."),
    ]


async def test_a_write_becomes_a_card_that_never_runs_and_an_interruption_is_stopped(
    turn_bench: TurnBench,
) -> None:
    person = uuid.uuid4()
    thread = uuid.UUID(await turn_bench.thread(person))
    start = VoiceStart(workspace_id=None, thread_id=thread, path=None, locale="en")
    talk = await voices(turn_bench).open(Principal(person, HOME, 0), start)
    heard = Heard()

    await talk.call("c-1", "tasks__create", '{"query": "Call Anna"}', heard)
    await talk.record(exchange("Remind me to call Anna.", "It is ready to", interrupted=True))
    await talk.record(exchange("", ""))

    assert talk.thread_id == thread
    assert len(heard.cards) == 1
    assert turn_bench.tools.executed == []
    messages = await fetch_rows(turn_bench.connection, MESSAGES, (thread,))
    assert [(m["role"], m["status"]) for m in messages] == [
        ("user", None),
        ("assistant", "stopped"),
    ]
    assert messages[-1]["action_ids"] == heard.cards
    assert len(await fetch_rows(turn_bench.connection, RUNS, (thread,))) == 1


async def test_voice_is_refused_when_switched_off_without_consent_or_in_another_space(
    turn_bench: TurnBench,
) -> None:
    person, stranger = uuid.uuid4(), uuid.uuid4()
    thread = uuid.UUID(await turn_bench.thread(person))
    turns = voices(turn_bench)
    elsewhere = VoiceStart(workspace_id=uuid.uuid4(), thread_id=thread, path=None, locale="en")
    theirs = VoiceStart(workspace_id=None, thread_id=thread, path=None, locale="en")

    with pytest.raises(AppError) as other_space:
        await turns.open(Principal(person, HOME, 0), elsewhere)
    with pytest.raises(AppError) as not_theirs:
        await turns.open(Principal(stranger, HOME, 0), theirs)
    with pytest.raises(AppError) as no_consent:
        await turns.open(Principal(uuid.uuid4(), Home.RU, 0), PLAIN)
    async with turn_bench.homes.transactions.begin(TenancyScope(HOME, person)) as session:
        session.add(AgentSettingsRecord(user_id=person, voice_mode=False))
    with pytest.raises(AppError) as switched_off:
        await turns.open(Principal(person, HOME, 0), theirs)

    assert [e.value.code for e in (other_space, not_theirs, no_consent, switched_off)] == [
        "thread_not_found", "thread_not_found", "consent_required", "voice_mode_off",
    ]  # fmt: skip

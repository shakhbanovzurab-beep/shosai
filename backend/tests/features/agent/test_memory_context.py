"""Memory in a turn's context: the profile core keeps segment 4 byte-identical, recalled facts
come before the question, only facts the person confirmed leave the run untainted, and a turn
carries memory's switch only while memory is on (memory steps 4 and 6, ADR 0071 MM-D7)."""

import uuid
from dataclasses import dataclass, field
from typing import Final

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.context import Taint
from shosai.core.agent_tools.provenance import Provenance
from shosai.core.ai.requests import ChatRequest, TextPart
from shosai.features.agent.contracts.memory import (
    MEMORY_SWITCH,
    ProfileCore,
    RecalledFact,
    RecallRequest,
)
from shosai.features.agent.infrastructure.prompts import MEMORY_OFF, MEMORY_ON, RECALLED
from tests.features.agent.bench_doubles import MemoryPorts
from tests.features.agent.turn_bench import TurnBench, stream_of
from tests.harness.connections import fetch_rows

RUN_TAINT: Final = "SELECT taint FROM agent_runs WHERE thread_id = %s ORDER BY started_at"
OWN: Final = RecalledFact("Prefers short answers", "preference", Provenance.MEMORY, Taint.NONE)
GUESSED: Final = RecalledFact("Works late", "fact", Provenance.MEMORY, Taint.EXTERNAL)
HEARD: Final = RecalledFact(
    "Mara leads design", "relationship", Provenance.MEETING_SPEECH, Taint.EXTERNAL
)


@dataclass
class Memory:
    """Memory as a turn sees it: what it recalls, its profile core, and what it was asked."""

    recalled: tuple[RecalledFact, ...] = ()
    pinned: tuple[RecalledFact, ...] = (OWN,)
    on: bool = True
    asked: list[RecallRequest] = field(default_factory=list)

    async def recall(self, request: RecallRequest) -> tuple[RecalledFact, ...]:
        """The facts for the question."""
        self.asked.append(request)
        return self.recalled

    async def profile(
        self, session: AsyncSession, user_id: uuid.UUID, max_tokens: int
    ) -> ProfileCore:
        """The profile core."""
        del session, user_id, max_tokens
        return ProfileCore(enabled=self.on, facts=self.pinned if self.on else ())

    async def enabled(self, session: AsyncSession, user_id: uuid.UUID) -> bool:
        """Whether memory is on."""
        del session, user_id
        return self.on


@pytest.fixture
def memory() -> Memory:
    """The memory bound for this module's turns."""
    return Memory()


@pytest.fixture
def memory_doubles(memory: Memory) -> tuple[MemoryPorts, ...]:
    """The module's memory."""
    return (memory,)


def text_at(request: ChatRequest, index: int) -> str:
    """The text of one message of a request."""
    return "".join(
        part.text for part in request.messages[index].parts if isinstance(part, TextPart)
    )


async def taints(turn_bench: TurnBench, thread: str) -> list[int]:
    """The final taint of each run of the thread, in order."""
    rows = await fetch_rows(turn_bench.connection, RUN_TAINT, (uuid.UUID(thread),))
    return [int(row["taint"]) for row in rows]


async def test_the_profile_core_keeps_the_head_byte_identical_and_trusts_the_persons_own(
    turn_bench: TurnBench, memory: Memory
) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)

    await turn_bench.ask(person, thread, "First question")
    await turn_bench.ask(person, thread, "Second question")
    memory.pinned = (OWN, GUESSED)
    await turn_bench.ask(person, thread, "Third question")
    first, second, third = turn_bench.model.calls[-3:]

    head = text_at(first, 0)
    assert MEMORY_ON in head
    assert MEMORY_SWITCH in turn_bench.queue.sent[-1].switches_on
    assert "- [preference] Prefers short answers" in head
    assert first.messages[0] == second.messages[0]
    assert third.messages[0] != first.messages[0]
    assert await taints(turn_bench, thread) == [Taint.NONE, Taint.NONE, Taint.EXTERNAL]


async def test_recalled_facts_come_before_the_question_with_their_labels(
    turn_bench: TurnBench, memory: Memory
) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    memory.recalled = (OWN, HEARD)

    events = stream_of(await turn_bench.ask(person, thread, "Who leads design?"))
    request = turn_bench.model.calls[-1]

    last = text_at(request, -1)
    assert events[-1][0] == "run.completed"
    assert last.index(RECALLED) < last.index("Who leads design?")
    assert "<<untrusted source=meeting:speech" in last
    assert "<<untrusted source=memory" in last
    assert memory.asked[-1].query == "Who leads design?"
    assert memory.asked[-1].user_id == person
    assert await taints(turn_bench, thread) == [Taint.EXTERNAL]


async def test_memory_off_says_so_and_recalls_nothing(
    turn_bench: TurnBench, memory: Memory
) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    memory.on, memory.recalled = False, (OWN,)

    await turn_bench.ask(person, thread, "Remember that I like tea")
    request = turn_bench.model.calls[-1]

    assert MEMORY_OFF in text_at(request, 0)
    assert RECALLED not in text_at(request, -1)
    assert memory.asked == []
    assert MEMORY_SWITCH not in turn_bench.queue.sent[-1].switches_on

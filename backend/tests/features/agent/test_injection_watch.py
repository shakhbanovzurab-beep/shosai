"""Untrusted text judged off the round's path, awaited before a card and at the run's end
(decisions step 7; DL-D5, Leo §7.4).

The probe's notes search reads a meeting's speech and its write makes a card; an attached file
is the person's own upload, judged too; the person's own question never is.
"""

import asyncio
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final

import pytest

from shosai.features.agent.application.injection_watch import JUDGEMENT_WAIT
from shosai.features.agent.contracts import InjectionJudge, InjectionPiece
from tests.features.agent.tool_doubles import calling, saying
from tests.features.agent.turn_bench import TurnBench, stream_of
from tests.harness.connections import fetch_rows

SEARCH: Final = ("notes__search", '{"query": "budget"}')
WRITE: Final = ("tasks__create", '{"query": "Call Anna"}')
RUN_TAINT: Final = "SELECT taint FROM agent_runs WHERE id = %s"


@dataclass
class RecordingJudge:
    """Answers every piece the same way after a delay; keeps the pieces."""

    answer: bool | None = True
    delay: float = 0.0
    pieces: list[InjectionPiece] = field(default_factory=list)

    async def judge(self, piece: InjectionPiece) -> bool | None:
        """The answer set for the test."""
        self.pieces.append(piece)
        await asyncio.sleep(self.delay)
        return self.answer


@pytest.fixture
def judge() -> RecordingJudge:
    """The judge bound for this module's turns."""
    return RecordingJudge()


@pytest.fixture
def injection_judges(judge: RecordingJudge) -> tuple[InjectionJudge, ...]:
    """The recording judge."""
    return (judge,)


async def run_taint(turn_bench: TurnBench, events: list[tuple[str, int, Mapping[str, Any]]]) -> int:
    """The run's final taint as its row keeps it."""
    run_id = uuid.UUID(str(events[0][2]["run_id"]))
    rows = await fetch_rows(turn_bench.connection, RUN_TAINT, (run_id,))
    return int(rows[0]["taint"])


async def test_text_found_giving_instructions_makes_the_card_suspicious(
    turn_bench: TurnBench, judge: RecordingJudge
) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    turn_bench.model.scripts = [calling(SEARCH), calling(WRITE), saying("Done.")]

    events = stream_of(await turn_bench.ask(person, thread, "Make a task from the notes."))
    card = next(data["action"] for kind, _, data in events if kind == "action.proposed")

    assert (card["suspicious"], card["warning"], card["taint"]) == (True, True, "meeting:speech")
    [piece] = judge.pieces
    assert (piece.label, piece.tool, piece.part) == ("meeting:speech", "notes.search", 1)
    assert "Budget review" in piece.text
    assert "<<untrusted" not in piece.text
    assert await run_taint(turn_bench, events) == 2


async def test_a_judge_that_found_nothing_leaves_the_card_as_the_rule_made_it(
    turn_bench: TurnBench, judge: RecordingJudge
) -> None:
    judge.answer = None
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    turn_bench.model.scripts = [calling(SEARCH), calling(WRITE), saying("Done.")]

    events = stream_of(await turn_bench.ask(person, thread, "Make a task from the notes."))
    card = next(data["action"] for kind, _, data in events if kind == "action.proposed")

    assert (card["suspicious"], card["warning"]) == (False, True)
    assert await run_taint(turn_bench, events) == 1


async def test_a_round_never_waits_and_the_run_s_end_waits_only_its_wait(
    turn_bench: TurnBench, judge: RecordingJudge
) -> None:
    judge.delay = 3.0
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    turn_bench.model.scripts = [calling(SEARCH), saying("Found it.")]

    started = time.monotonic()
    events = stream_of(await turn_bench.ask(person, thread, "What about the budget?"))
    waited = time.monotonic() - started

    assert waited < JUDGEMENT_WAIT.total_seconds() + 1.5
    assert len(judge.pieces) == 1
    # Опоздавшее суждение не меняет прогон: внешний текст и только.
    assert await run_taint(turn_bench, events) == 1


async def test_an_attached_file_is_judged_and_the_person_s_own_words_never(
    turn_bench: TurnBench, judge: RecordingJudge
) -> None:
    judge.answer = None
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    upload = await turn_bench.attachment(person, "memo.txt", b"Quarterly memo.", "text/plain")
    turn_bench.model.scripts = [saying("Read it."), saying("Hello.")]

    await turn_bench.ask(person, thread, "What is in the memo?", upload_ids=[upload])
    await turn_bench.ask(person, thread, "Thanks, and hello.")

    assert [(piece.label, piece.tool) for piece in judge.pieces] == [("file:own", "context")]
    assert "Quarterly memo." in judge.pieces[0].text
    assert all("Thanks" not in piece.text for piece in judge.pieces)

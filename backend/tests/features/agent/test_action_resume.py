"""A paused run after its card's decision: the epilogue in the same run, or its close (Leo §5.3;
agent step 9a2).

An approved card's action runs, then its run resumes from the frame: the model reads what
became of the action and writes the epilogue on the same run's stream, the answer follows the
server note and the frame is deleted. A lost frame closes the run with its note instead; a new
turn closes the paused run, and the old card still executes with a note; two deliveries of a
resume drive one epilogue; a rejected card ends its run without one.
"""

import asyncio
import uuid
from collections.abc import Sequence
from typing import Final

from shosai.core.ai.requests import ChatMessage
from shosai.features.agent.application.run_resumption import ResumePayload
from shosai.features.agent.infrastructure.run_keys import checkpoint_key
from tests.features.agent.action_bench import ActionBench
from tests.features.agent.tool_doubles import saying
from tests.features.agent.turn_bench import HOME, stream_of
from tests.features.billing.people_bench import bearer

RUN_ROW: Final = "SELECT status, outcome_code, rounds FROM agent_runs WHERE id = %s"
THREAD_ROWS: Final = (
    "SELECT role, text FROM agent_messages WHERE thread_id = %s AND role IN "
    "('user', 'assistant', 'server') AND tool_calls IS NULL ORDER BY created_at, id"
)


def texts_of(messages: Sequence[ChatMessage]) -> list[str]:
    """The texts of a model call's messages."""
    return ["".join(getattr(part, "text", "") for part in message.parts) for message in messages]


async def test_an_approved_card_resumes_its_run_and_the_model_writes_the_epilogue(
    action_bench: ActionBench,
) -> None:
    person = uuid.uuid4()
    turn = await action_bench.paused_turn(person)
    run_id = uuid.UUID(turn["run_id"])
    calls_before = len(action_bench.turns.model.calls)

    approved = await action_bench.decide(person, turn["card"], "approve")
    await action_bench.queue.settle()
    tail = await action_bench.turns.http.get(
        f"/v1/agent/runs/{run_id}/events",
        headers=bearer((HOME, person)) | {"Last-Event-ID": str(turn["events"][-1][1])},
    )
    events = stream_of(tail)
    epilogue_call = action_bench.turns.model.calls[calls_before]
    run = (await action_bench.rows(RUN_ROW, run_id))[0]
    rows = await action_bench.rows(THREAD_ROWS, uuid.UUID(turn["thread"]))

    assert approved.json()["status"] == "succeeded"
    assert [kind for kind, _, _ in events] == [
        "action.updated", "action.updated", "text.delta", "run.completed",
    ]  # fmt: skip
    assert events[-1][2]["outcome"] == "answered"
    assert any(
        text.endswith("with tasks.create was approved and done.")
        for text in texts_of(epilogue_call.messages)
    )
    assert (run["status"], run["outcome_code"], run["rounds"]) == ("completed", "answered", 2)
    assert [row["role"] for row in rows] == ["user", "server", "assistant"]
    assert rows[-1]["text"] == "Done."
    assert not await action_bench.turns.valkey.exists(checkpoint_key(run_id))


async def test_a_lost_frame_closes_the_run_with_its_note(action_bench: ActionBench) -> None:
    person = uuid.uuid4()
    turn = await action_bench.paused_turn(person)
    run_id = uuid.UUID(turn["run_id"])
    await action_bench.turns.valkey.delete(checkpoint_key(run_id))
    calls_before = len(action_bench.turns.model.calls)

    await action_bench.decide(person, turn["card"], "approve")
    await action_bench.queue.settle()
    run = (await action_bench.rows(RUN_ROW, run_id))[0]
    rows = await action_bench.rows(THREAD_ROWS, uuid.UUID(turn["thread"]))

    assert len(action_bench.turns.model.calls) == calls_before
    assert (run["status"], run["outcome_code"]) == ("completed", "checkpoint_lost")
    assert [row["role"] for row in rows] == ["user", "assistant", "server"]


async def test_a_new_turn_closes_the_paused_run_and_the_old_card_still_executes(
    action_bench: ActionBench,
) -> None:
    person = uuid.uuid4()
    turn = await action_bench.paused_turn(person)
    run_id = uuid.UUID(turn["run_id"])
    action_bench.turns.model.scripts = [saying("Hi.")]
    await action_bench.turns.ask(person, turn["thread"], "Something else.")
    closed = (await action_bench.rows(RUN_ROW, run_id))[0]
    calls_before = len(action_bench.turns.model.calls)

    approved = await action_bench.decide(person, turn["card"], "approve")
    await action_bench.queue.settle()
    notes = await action_bench.rows(
        "SELECT digest FROM agent_messages WHERE run_id = %s AND role = 'server'", run_id
    )

    assert (closed["status"], closed["outcome_code"]) == ("completed", "new_turn")
    assert approved.json()["status"] == "succeeded"
    assert action_bench.turns.tools.executed == [f"{turn['card']['id']}:0"]
    assert len(action_bench.turns.model.calls) == calls_before
    assert notes[0]["digest"]["text"].endswith("was approved and done.")
    assert not await action_bench.turns.valkey.exists(checkpoint_key(run_id))


async def test_two_deliveries_of_a_resume_drive_one_epilogue(action_bench: ActionBench) -> None:
    person = uuid.uuid4()
    action_bench.queue.hold_resumes = True
    turn = await action_bench.paused_turn(person)
    await action_bench.decide(person, turn["card"], "approve")
    await action_bench.queue.settle()
    (resume,) = action_bench.queue.resumes
    calls_before = len(action_bench.turns.model.calls)

    engine = action_bench.turns.queue.engine
    assert engine is not None
    await asyncio.gather(*(engine.resume(resume) for _ in range(2)))
    run = (await action_bench.rows(RUN_ROW, uuid.UUID(turn["run_id"])))[0]

    assert isinstance(resume, ResumePayload)
    assert len(action_bench.turns.model.calls) == calls_before + 1
    assert (run["status"], run["outcome_code"]) == ("completed", "answered")


async def test_a_rejected_card_ends_its_run_without_an_epilogue(action_bench: ActionBench) -> None:
    person = uuid.uuid4()
    turn = await action_bench.paused_turn(person)
    run_id = uuid.UUID(turn["run_id"])
    calls_before = len(action_bench.turns.model.calls)

    await action_bench.decide(person, turn["card"], "reject")
    await action_bench.queue.settle()
    run = (await action_bench.rows(RUN_ROW, run_id))[0]

    assert len(action_bench.turns.model.calls) == calls_before
    assert (run["status"], run["outcome_code"]) == ("completed", "decided")
    assert not await action_bench.turns.valkey.exists(checkpoint_key(run_id))

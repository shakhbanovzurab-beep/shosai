"""The turn's frame with our saver: a loop to the answer, the pause on a card and the resume
(ADR 0068 AG-D14; agent step 9a2).

A turn that proposes a write stops paused with its terms kept in Valkey — references only — and
resumes in another process's frame from there, with the action decided: the round that paused
is not run again, the model writes the epilogue, and a forgotten frame cannot resume. A Valkey
that does not answer costs the epilogue, never the turn.
"""

import uuid
from typing import Final
from uuid import UUID

from redis.asyncio import Redis

from shosai.core.ai.requests import ToolCall
from shosai.features.agent.infrastructure.run_keys import checkpoint_key
from shosai.features.agent.infrastructure.turn_frame_fields import as_bytes
from shosai.features.agent.infrastructure.turn_graph import (
    ModelAnswer,
    paused_terms,
    resume_turn,
    run_turn,
    turn_graph,
)
from shosai.features.agent.infrastructure.turn_saver import TurnSaver

CALL: Final = ToolCall("call-1", "tasks__create", "{}")
TERMS: Final = {"run_id": "terms of the turn", "language": "en"}


class Steps:
    """The nodes' work for a test: `calls` rounds with a call, a card after `card_after` tool
    rounds, then an answer; the order of what ran."""

    def __init__(self, calls: int, card_after: int | None = None) -> None:
        self.order: list[str] = []
        self.calls = calls
        self.card_after = card_after
        self.action = uuid.uuid4()
        self.answers: list[ModelAnswer] = []

    async def context(self) -> None:
        self.order.append("context")

    async def model(self) -> ModelAnswer:
        self.order.append("model")
        if self.order.count("model") <= self.calls:
            answer = ModelAnswer("", "tool_calls", None, None, tool_calls=(CALL,))
        else:
            answer = ModelAnswer("Hello", "length", None, 5)
        self.answers.append(answer)
        return answer

    async def tools(self) -> UUID | None:
        self.order.append("tools")
        if self.card_after is not None and self.order.count("tools") == self.card_after:
            return self.action
        return None

    async def resume(self, action_id: UUID) -> None:
        self.order.append(f"resume:{action_id}")

    def answer(self) -> ModelAnswer | None:
        return self.answers[-1] if self.answers else None


async def test_the_frame_loops_through_tools_until_the_model_answers(valkey: Redis) -> None:
    steps, run_id = Steps(calls=2), uuid.uuid4()

    kept = await run_turn(turn_graph(TurnSaver(valkey)), steps, run_id, dict(TERMS))

    assert steps.order == ["context", "model", "tools", "model", "tools", "model"]
    assert (kept.model.text, kept.truncated, kept.paused) == ("Hello", True, None)
    await TurnSaver(valkey).forget(run_id)
    assert not await valkey.exists(checkpoint_key(run_id))


async def test_a_card_pauses_the_frame_and_the_decision_resumes_it_elsewhere(
    valkey: Redis,
) -> None:
    first, run_id = Steps(calls=1, card_after=1), uuid.uuid4()

    paused = await run_turn(turn_graph(TurnSaver(valkey)), first, run_id, dict(TERMS))
    kept_terms = await paused_terms(turn_graph(TurnSaver(valkey)), run_id)
    ttl = await valkey.pttl(checkpoint_key(run_id))
    later = Steps(calls=0)
    resumed = await resume_turn(turn_graph(TurnSaver(valkey)), later, run_id, first.action)

    assert first.order == ["context", "model", "tools"]
    assert paused.paused == first.action
    assert kept_terms == TERMS
    assert 70 * 60_000 < ttl <= 75 * 60_000
    assert later.order == [f"resume:{first.action}", "model"]
    assert (resumed.model.text, resumed.paused) == ("Hello", None)
    await TurnSaver(valkey).forget(run_id)
    assert await paused_terms(turn_graph(TurnSaver(valkey)), run_id) is None


async def test_the_frame_saves_references_only(valkey: Redis) -> None:
    steps, run_id = Steps(calls=1, card_after=1), uuid.uuid4()

    await run_turn(turn_graph(TurnSaver(valkey)), steps, run_id, dict(TERMS))
    saved = [as_bytes(value) for value in (await valkey.hgetall(checkpoint_key(run_id))).values()]

    assert sum(len(value) for value in saved) < 4_000
    assert b"Hello" not in b"".join(saved)
    await TurnSaver(valkey).forget(run_id)


async def test_a_silent_valkey_pauses_the_turn_without_its_frame() -> None:
    steps, run_id = Steps(calls=1, card_after=1), uuid.uuid4()
    silent = Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.2)
    graph = turn_graph(TurnSaver(silent))

    try:
        paused = await run_turn(graph, steps, run_id, dict(TERMS))
        kept = await paused_terms(graph, run_id)
    finally:
        await silent.aclose()

    assert paused.paused == steps.action
    assert kept is None

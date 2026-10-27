"""A card approved by voice (LEO-voice step 8; Leo §8.4, Q-6 decided by the owner).

A write in a voice exchange becomes a card that Leo reads back from the server's rendering. It
is approved by voice only when the voice model calls `core.confirm` for that card and the bound
judge finds the person's words, as the server heard them, a clear yes; then it goes the
screen's way with `approved_via = voice`. Everything else leaves it on the screen (A2). Until
the judge can find a yes — no active version — Leo does not ask for one; after a second reply
that is not a clear yes, Leo sends the card to the screen instead of asking again.
"""

import json
import uuid
from typing import Any

from shosai.features.agent.contracts.voice import VoiceStart
from shosai.features.agent.infrastructure.voice_prompts import (
    CARD_BY_VOICE,
    CARD_ON_SCREEN,
    NOT_APPROVED,
    SCREEN_ONLY,
    STILL_UNCLEAR,
)
from shosai.features.identity.contracts import Principal
from tests.features.agent.action_bench import ActionBench
from tests.features.agent.turn_bench import HOME
from tests.features.agent.voice_doubles import ApprovalJudge, Heard, agent_voices

PLAIN = VoiceStart(workspace_id=None, thread_id=None, path=None, locale="en")
WRITE = ("c-1", "tasks__create", '{"query": "Call Anna"}')
# Чтение речи встречи — чужой текст: запись после него получает предупреждение.
SPEECH = ("c-0", "notes__search", '{"query": "Anna"}')


def confirm(action_id: object) -> tuple[str, str, str]:
    """The voice model's `core.confirm` of a card."""
    return ("c-2", "core__confirm", json.dumps({"action_id": str(action_id)}))


async def card_row(bench: ActionBench, action_id: str) -> dict[str, Any]:
    """The card's status and channel, and its audit's channels."""
    [row] = await bench.rows(
        "SELECT status, approved_via FROM agent_actions WHERE id = %s", action_id
    )
    audit = await bench.rows("SELECT event, via FROM agent_audit WHERE action_id = %s", action_id)
    return row | {"audit": sorted((a["event"], a["via"]) for a in audit)}


async def test_a_card_read_back_is_approved_by_voice_and_carried_out(
    action_bench: ActionBench,
) -> None:
    judge = ApprovalJudge(verdict=True)
    talk = await agent_voices(action_bench, judge).open(Principal(uuid.uuid4(), HOME, 0), PLAIN)
    heard = Heard()

    told = json.loads(await talk.call(WRITE, heard, heard="Remind me to call Anna."))
    card = told["card"]
    done = json.loads(await talk.call(confirm(card["action_id"]), heard, heard=" Yes, do it. "))
    await action_bench.queue.settle()

    assert "core__confirm" in {tool.name for tool in talk.tools}
    assert (card["next"], card["read_back"]) == (CARD_BY_VOICE, "Probe write\nTasks: 1")
    assert done["status"] in {"executing", "succeeded"}
    [facts] = judge.heard
    assert (facts.read_back, facts.utterance, facts.language) == (
        "Probe write\nTasks: 1", "Yes, do it.", "en",
    )  # fmt: skip
    assert action_bench.turns.tools.executed == [f"{card['action_id']}:0"]
    row = await card_row(action_bench, card["action_id"])
    assert (row["status"], row["approved_via"]) == ("succeeded", "voice")
    assert ("approved", "voice") in row["audit"]
    assert heard.approvals == [uuid.UUID(card["action_id"])]


async def test_no_clear_yes_no_judge_a_warning_or_an_unread_card_leaves_it_on_the_screen(
    action_bench: ActionBench,
) -> None:
    person = Principal(uuid.uuid4(), HOME, 0)
    doubtful = await agent_voices(action_bench, ApprovalJudge(verdict=None)).open(person, PLAIN)
    alone = await agent_voices(action_bench).open(person, PLAIN)
    tainted = await agent_voices(action_bench, ApprovalJudge(verdict=True)).open(person, PLAIN)
    heard = Heard()

    first = json.loads(await doubtful.call(WRITE, heard, heard="Call Anna."))["card"]
    unsure = json.loads(
        await doubtful.call(confirm(first["action_id"]), heard, heard="Hmm, maybe.")
    )
    silent = json.loads(await doubtful.call(confirm(first["action_id"]), heard, heard="  "))
    second = json.loads(await alone.call(WRITE, heard, heard="Call Anna."))["card"]
    unjudged = json.loads(await alone.call(confirm(second["action_id"]), heard, heard="Yes."))
    await tainted.call(SPEECH, heard, heard="What did Anna say?")
    third = json.loads(await tainted.call(WRITE, heard, heard="Call her."))["card"]
    warned = json.loads(await tainted.call(confirm(third["action_id"]), heard, heard="Yes."))
    unread = json.loads(await tainted.call(confirm(first["action_id"]), heard, heard="Yes."))

    assert [unsure["next"], silent["next"]] == [NOT_APPROVED, STILL_UNCLEAR]
    assert (second["next"], unjudged["next"]) == (CARD_ON_SCREEN, SCREEN_ONLY)
    assert "core__confirm" not in {tool.name for tool in alone.tools}
    assert (third["next"], warned["next"], unread["next"]) == (
        CARD_ON_SCREEN, SCREEN_ONLY, SCREEN_ONLY,
    )  # fmt: skip
    assert action_bench.turns.tools.executed == []
    assert heard.approvals == []
    for card in (first, second, third):
        row = await card_row(action_bench, card["action_id"])
        assert (row["status"], row["approved_via"]) == ("proposed", None)


async def test_without_an_active_version_leo_sends_the_card_to_the_screen_at_once(
    action_bench: ActionBench,
) -> None:
    person = Principal(uuid.uuid4(), HOME, 0)
    judge = ApprovalJudge(verdict=True, active=False)
    talk = await agent_voices(action_bench, judge).open(person, PLAIN)
    heard = Heard()

    card = json.loads(await talk.call(WRITE, heard, heard="Remind me to call Anna."))["card"]
    asked = json.loads(await talk.call(confirm(card["action_id"]), heard, heard="Yes."))

    assert "core__confirm" not in {tool.name for tool in talk.tools}
    assert (card["next"], asked["next"]) == (CARD_ON_SCREEN, SCREEN_ONLY)
    assert judge.heard == []
    row = await card_row(action_bench, card["action_id"])
    assert (row["status"], row["approved_via"]) == ("proposed", None)


async def test_after_two_unclear_replies_the_card_goes_to_the_screen(
    action_bench: ActionBench,
) -> None:
    person = Principal(uuid.uuid4(), HOME, 0)
    judge = ApprovalJudge(verdict=None)
    talk = await agent_voices(action_bench, judge).open(person, PLAIN)
    heard = Heard()

    card = json.loads(await talk.call(WRITE, heard, heard="Call Anna."))["card"]
    replies = [
        json.loads(await talk.call(confirm(card["action_id"]), heard, heard=said))["next"]
        for said in ("Project again.", "Yes.", "Yes, I confirm.")
    ]

    assert card["next"] == CARD_BY_VOICE
    assert replies == [NOT_APPROVED, STILL_UNCLEAR, SCREEN_ONLY]
    assert len(judge.heard) == 2
    assert heard.approvals == []

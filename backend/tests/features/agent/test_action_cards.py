"""The person's cards in their language: in the stream, the inbox, the history (agent step 9b).

A card carries its slice's words for the planned write, the space it goes to in the person's
language, where it came from and its nonce, the same in the stream and over HTTP. The inbox
lists only the person's own cards newest first by cursor; "Needs you" offers only cards still
waiting within their hour; a stranger's card is not found. The history's answer carries the
card it proposed, as it stands now. A card that has run names the cabinet's data it changed,
so a decision outside a run's stream — a voice card's, one whose log is gone — still refreshes
the screens.
"""

import uuid
from typing import Any, Final

from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER
from tests.features.agent.action_bench import ActionBench
from tests.features.agent.turn_bench import HOME
from tests.features.agent.turn_doubles import Profiles
from tests.features.billing.people_bench import bearer

EXPIRED: Final = "UPDATE agent_actions SET expires_at = now() - interval '1 second' WHERE id = %s"


def speaks(bench: ActionBench, person: uuid.UUID, language: str) -> None:
    """The person's profile is in the language."""
    profiles = bench.turns.ports.get(ACCOUNT_PROFILE_READER)
    assert isinstance(profiles, Profiles)
    profiles.languages[person] = language


def without_times(card: dict[str, Any]) -> dict[str, Any]:
    """A card but its moments, whose JSON spelling differs between the stream and HTTP."""
    return {key: value for key, value in card.items() if not key.endswith("_at")}


async def inbox(bench: ActionBench, person: uuid.UUID, query: str = "") -> dict[str, Any]:
    """The person's inbox page."""
    answer = await bench.http.get(f"/v1/agent/actions{query}", headers=bearer((HOME, person)))
    assert answer.status_code == 200, answer.text
    page: dict[str, Any] = answer.json()
    return page


async def test_a_card_reads_in_the_person_s_language_everywhere(action_bench: ActionBench) -> None:
    person = uuid.uuid4()
    speaks(action_bench, person, "ru")
    turn = await action_bench.paused_turn(person)
    streamed = turn["card"]

    read = await action_bench.http.get(
        f"/v1/agent/actions/{streamed['id']}", headers=bearer((HOME, person))
    )
    stranger = await action_bench.http.get(
        f"/v1/agent/actions/{streamed['id']}", headers=bearer((HOME, uuid.uuid4()))
    )

    assert {key: streamed[key] for key in ("tool", "title", "space", "origin", "status")} == {
        "tool": "tasks.create", "title": "Probe write", "space": "Личное",
        "origin": {"kind": "thread", "app": None}, "status": "proposed",
    }  # fmt: skip
    assert streamed["preview"] == {
        "kind": "fields", "fields": [{"label": "Tasks", "value": "1"}], "body": None,
    }  # fmt: skip
    assert without_times(read.json()) == without_times(streamed)
    assert (stranger.status_code, stranger.json()["error"]["code"]) == (404, "action_not_found")


async def test_the_inbox_lists_the_person_s_waiting_cards_by_cursor(
    action_bench: ActionBench,
) -> None:
    person, other = uuid.uuid4(), uuid.uuid4()
    first = (await action_bench.paused_turn(person))["card"]
    rejected = (await action_bench.paused_turn(person))["card"]
    expired = (await action_bench.paused_turn(person))["card"]
    newest = (await action_bench.paused_turn(person))["card"]
    await action_bench.paused_turn(other)
    await action_bench.decide(person, rejected, "reject")
    await action_bench.move(EXPIRED, uuid.UUID(expired["id"]))

    page = await inbox(action_bench, person, "?status=proposed&limit=1")
    rest = await inbox(action_bench, person, f"?status=proposed&cursor={page['next_cursor']}")
    everything = await inbox(action_bench, person)

    assert [card["id"] for card in page["items"]] == [newest["id"]]
    assert [card["id"] for card in rest["items"]] == [first["id"]]
    assert rest["next_cursor"] is None
    assert [card["id"] for card in everything["items"]] == [
        newest["id"], expired["id"], rejected["id"], first["id"],
    ]  # fmt: skip
    assert [card["status"] for card in everything["items"]][2] == "rejected"


async def test_the_history_s_answer_carries_its_card_as_it_stands(
    action_bench: ActionBench,
) -> None:
    person = uuid.uuid4()
    turn = await action_bench.paused_turn(person)
    await action_bench.decide(person, turn["card"], "reject")

    history = await action_bench.turns.http.get(
        f"/v1/agent/threads/{turn['thread']}/messages", headers=bearer((HOME, person))
    )
    with_cards = [
        (message["role"], [card["status"] for card in message["actions"]])
        for message in history.json()["items"]
        if message["actions"]
    ]

    assert with_cards == [("server", ["rejected"]), ("assistant", ["rejected"])]


async def test_a_card_names_the_data_it_changed_once_it_has_run(action_bench: ActionBench) -> None:
    person = uuid.uuid4()
    waiting = (await action_bench.paused_turn(person))["card"]
    rejected = (await action_bench.paused_turn(person))["card"]

    approved = await action_bench.decide(person, waiting, "approve")
    await action_bench.queue.settle()
    refused = await action_bench.decide(person, rejected, "reject")
    read = await action_bench.http.get(
        f"/v1/agent/actions/{waiting['id']}", headers=bearer((HOME, person))
    )

    assert (waiting["status"], waiting["invalidates"]) == ("proposed", [])
    assert (approved.json()["status"], approved.json()["invalidates"]) == ("succeeded", ["tasks"])
    assert read.json()["invalidates"] == ["tasks"]
    assert (refused.json()["status"], refused.json()["invalidates"]) == ("rejected", [])

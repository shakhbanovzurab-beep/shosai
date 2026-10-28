"""A person's prompts on `/v1/studio/prompts*` (studio step 8): written once per key, their
skills the person's installed ones in order and within the role's budget, one prompt per role
of its own role, the role released when the prompt moves or goes, at most 100 a person."""

import asyncio
import uuid

import httpx

from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.studio.infrastructure.person_records import PromptRecord
from tests.features.billing.people_bench import bearer
from tests.features.studio.person_bench import PersonBench, someone

PROMPTS = "/v1/studio/prompts"


def code(reply: httpx.Response) -> tuple[int, str]:
    """The status and the error code of an answer."""
    return reply.status_code, reply.json()["error"]["code"]


async def test_a_create_runs_once_per_key_and_keeps_the_skills_in_order(
    person_bench: PersonBench,
) -> None:
    person = someone()
    first, second = (
        await person_bench.install(person, "pdf"),
        await person_bench.install(person, "xlsx"),
    )
    body = {"name": "  Interview  ", "role": "live_answers", "content": " Be brief. ",
            "skill_ids": [str(second), str(first), str(second)]}  # fmt: skip

    made = await person_bench.create(person, body, "k1")
    again = await person_bench.create(person, body, "k1")
    other = await person_bench.create(person, body | {"name": "Other"}, "k1")
    listed = (await person_bench.http.get(PROMPTS, headers=bearer(person))).json()

    assert (made.status_code, again.status_code) == (201, 201)
    prompt = made.json()
    assert (prompt["name"], prompt["content"]) == ("Interview", "Be brief.")
    assert prompt["skill_ids"] == [str(second), str(first)]
    assert again.json()["id"] == prompt["id"]
    assert code(other) == (422, "idempotency_key_reused")
    assert [item["id"] for item in listed["prompts"]] == [prompt["id"]]
    assert set(listed["active"].values()) == {None}


async def test_skills_must_be_installed_and_fit_the_budget(person_bench: PersonBench) -> None:
    person, stranger = someone(), someone()
    theirs = await person_bench.install(stranger, "theirs")
    huge = await person_bench.install(person, "huge", "x" * 24_000)
    base = {"name": "Code", "role": "code"}

    blank = await person_bench.create(person, {"name": "   ", "role": "code"})
    foreign = await person_bench.create(person, base | {"skill_ids": [str(theirs)]})
    over = await person_bench.create(
        person, base | {"content": "y" * 20_000, "skill_ids": [str(huge)]}
    )
    fits = await person_bench.create(
        person, base | {"content": "y" * 9_000, "skill_ids": [str(huge)]}
    )

    assert code(blank) == (422, "prompt_name_required")
    assert code(foreign) == (422, "skill_not_installed")
    assert foreign.json()["error"]["params"] == {"skill_id": str(theirs)}
    assert code(over) == (422, "prompt_over_budget")
    assert over.json()["error"]["params"] == {"tokens": 14_691, "max": 12_000}
    assert fits.status_code == 201


async def test_a_role_plays_by_a_prompt_of_its_own_role_until_it_moves_or_goes(
    person_bench: PersonBench,
) -> None:
    person = someone()
    headers = bearer(person)
    notes = (await person_bench.create(person, {"name": "Notes", "role": "notes"})).json()
    code_prompt = (await person_bench.create(person, {"name": "Code", "role": "code"})).json()

    async def choose(role: str, prompt_id: str | None) -> httpx.Response:
        body = {"role": role, "prompt_id": prompt_id}
        return await person_bench.http.put(f"{PROMPTS}/active", json=body, headers=headers)

    chosen = await choose("notes", notes["id"])
    wrong = await choose("code", notes["id"])
    await choose("code", code_prompt["id"])
    moved = await person_bench.http.patch(
        f"{PROMPTS}/{notes['id']}", json={"role": "system_design"}, headers=headers
    )
    after_move = (await person_bench.http.get(PROMPTS, headers=headers)).json()["active"]
    gone = await person_bench.http.delete(f"{PROMPTS}/{code_prompt['id']}", headers=headers)
    after_delete = (await person_bench.http.get(PROMPTS, headers=headers)).json()

    assert chosen.json()["active"]["notes"] == notes["id"]
    assert code(wrong) == (422, "prompt_for_other_role")
    assert moved.json()["role"] == "system_design"
    assert (after_move["notes"], after_move["code"]) == (None, code_prompt["id"])
    assert gone.status_code == 204
    assert after_delete["active"]["code"] is None
    assert [item["id"] for item in after_delete["prompts"]] == [notes["id"]]


async def test_an_edit_checks_the_skills_and_the_last_changed_lists_first(
    person_bench: PersonBench,
) -> None:
    person = someone()
    headers = bearer(person)
    skill = await person_bench.install(person, "pdf")
    older = (await person_bench.create(person, {"name": "Older", "role": "notes"})).json()
    newer = (await person_bench.create(person, {"name": "Newer", "role": "notes"})).json()

    edited = await person_bench.http.patch(
        f"{PROMPTS}/{older['id']}", json={"skill_ids": [str(skill)]}, headers=headers
    )
    refused = await person_bench.http.patch(
        f"{PROMPTS}/{older['id']}", json={"skill_ids": [str(uuid.uuid4())]}, headers=headers
    )
    listed = (await person_bench.http.get(PROMPTS, headers=headers)).json()["prompts"]

    assert edited.json()["skill_ids"] == [str(skill)]
    assert code(refused) == (422, "skill_not_installed")
    assert [item["id"] for item in listed] == [older["id"], newer["id"]]
    assert listed[0]["skill_ids"] == [str(skill)]


async def test_a_hundred_prompts_and_not_one_more_even_at_once(person_bench: PersonBench) -> None:
    home, user_id = person = someone()
    async with person_bench.homes.transactions.begin(TenancyScope(home, user_id)) as session:
        session.add_all(
            PromptRecord(id=uuid.uuid4(), user_id=user_id, name=f"P{n}", role="code", content="")
            for n in range(99)
        )

    replies = await asyncio.gather(
        person_bench.create(person, {"name": "A", "role": "code"}),
        person_bench.create(person, {"name": "B", "role": "code"}),
    )

    assert sorted(reply.status_code for reply in replies) == [201, 409]
    refused = next(reply for reply in replies if reply.status_code == 409)
    assert refused.json()["error"] == refused.json()["error"] | {
        "code": "prompt_limit_reached",
        "params": {"max": 100},
    }

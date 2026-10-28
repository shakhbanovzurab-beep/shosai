"""Everything in Studio is the person's own (studio step 8, ADR 0053): another person's prompt
is `prompt_not_found` on every route that names it and absent from every list, in their home
or another, and nobody reads another's context or settings."""

import pytest

from shosai.core.kernel.homes import Home
from tests.features.billing.people_bench import bearer
from tests.features.studio.person_bench import Person, PersonBench, someone

PROMPTS = "/v1/studio/prompts"


async def owned_prompt(bench: PersonBench, owner: Person) -> str:
    """The owner's prompt, active for its role, with their context and a role's settings."""
    headers = bearer(owner)
    prompt = (
        await bench.create(owner, {"name": "Mine", "role": "notes", "content": "Secret."})
    ).json()
    await bench.http.put(
        f"{PROMPTS}/active", json={"role": "notes", "prompt_id": prompt["id"]}, headers=headers
    )
    await bench.http.put("/v1/studio/context", json={"content": "Mine."}, headers=headers)
    return str(prompt["id"])


@pytest.mark.parametrize("home", [Home.RU, Home.EU])
async def test_another_person_s_prompt_is_not_found_on_every_route(
    person_bench: PersonBench, home: Home
) -> None:
    owner, stranger = someone(Home.RU), someone(home)
    prompt_id = await owned_prompt(person_bench, owner)
    headers = bearer(stranger)
    http = person_bench.http

    answers = [
        await http.patch(f"{PROMPTS}/{prompt_id}", json={"name": "Theirs"}, headers=headers),
        await http.delete(f"{PROMPTS}/{prompt_id}", headers=headers),
        await http.put(
            f"{PROMPTS}/active", json={"role": "notes", "prompt_id": prompt_id}, headers=headers
        ),
    ]
    listed = (await http.get(PROMPTS, headers=headers)).json()
    context = (await http.get("/v1/studio/context", headers=headers)).json()
    owners = (await http.get(PROMPTS, headers=bearer(owner))).json()

    assert [(answer.status_code, answer.json()["error"]["code"]) for answer in answers] == [
        (404, "prompt_not_found")
    ] * 3
    assert listed["prompts"] == []
    assert set(listed["active"].values()) == {None}
    assert context == {"content": "", "updated_at": None}
    assert owners["prompts"][0]["name"] == "Mine"
    assert owners["active"]["notes"] == prompt_id


async def test_every_route_needs_the_person_s_token(person_bench: PersonBench) -> None:
    http = person_bench.http
    answers = [
        await http.get("/v1/studio/context"),
        await http.get(PROMPTS),
        await http.post(PROMPTS, json={"name": "A", "role": "code"}),
        await http.get("/v1/studio/models"),
    ]

    assert {answer.status_code for answer in answers} == {401}

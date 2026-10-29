"""A person's context and model settings on `/v1/studio/*` (studio step 8): the context stored
trimmed, the models on the person's plan, each role's settings checked against the plan, the
role and the model, and an unreadable plan refused rather than guessed (inv-3)."""

from datetime import UTC, datetime

import httpx

from shosai.core.events.subscriptions import ReceivedEvent
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.agent.contracts.events import SkillRemoved
from shosai.features.studio.channels.subscriptions import skill_removed
from shosai.features.studio.domain.roles import Tier
from tests.features.billing.people_bench import bearer
from tests.features.studio.catalogue_bench import entry, openrouter_list
from tests.features.studio.person_bench import PersonBench, someone

FLASH, SONNET, SMALL = "google/gemini-3.8-flash", "anthropic/claude-sonnet-5", "mistral/small-4"


def code(reply: httpx.Response) -> tuple[int, str]:
    """The status and the error code of an answer."""
    return reply.status_code, reply.json()["error"]["code"]


async def catalogue(bench: PersonBench) -> dict[str, str]:
    """Three models switched on — a frontier one and a text-only one — by OpenRouter id."""
    entries = (entry(FLASH, image=True), entry(SONNET, image=True), entry(SMALL))
    ids = {}
    for model_id, tier in ((FLASH, Tier.STANDARD), (SONNET, Tier.FRONTIER), (SMALL, Tier.STANDARD)):
        bench.catalogue.lists(openrouter_list(*entries))
        model = await bench.catalogue.admin.add(model_id, tier)
        await bench.catalogue.admin.switch(model.id, enabled=True)
        ids[model_id] = model.id
    return ids


async def test_the_context_is_stored_trimmed_and_bounded(person_bench: PersonBench) -> None:
    headers = bearer(someone())
    before = (await person_bench.http.get("/v1/studio/context", headers=headers)).json()

    saved = await person_bench.http.put(
        "/v1/studio/context", json={"content": "  I lead a design team.  "}, headers=headers
    )
    too_long = await person_bench.http.put(
        "/v1/studio/context", json={"content": "x" * 4_001}, headers=headers
    )
    after = (await person_bench.http.get("/v1/studio/context", headers=headers)).json()

    assert before == {"content": "", "updated_at": None, "roles": "all"}
    assert saved.json()["content"] == "I lead a design team."
    assert too_long.status_code == 422
    assert after == saved.json()


async def test_the_roles_that_take_the_context_are_chosen_and_the_words_stay(
    person_bench: PersonBench,
) -> None:
    headers = bearer(someone())
    roles = "/v1/studio/context/roles"

    first = await person_bench.http.put(
        roles, json={"roles": ["code", "live_answers", "code"]}, headers=headers
    )
    worded = await person_bench.http.put(
        "/v1/studio/context", json={"content": "I lead a design team."}, headers=headers
    )
    every = await person_bench.http.put(roles, json={"roles": "all"}, headers=headers)
    none = await person_bench.http.put(roles, json={"roles": []}, headers=headers)
    unknown = await person_bench.http.put(roles, json={"roles": ["leo"]}, headers=headers)
    some = await person_bench.http.put(roles, json={"roles": "some"}, headers=headers)

    assert (first.json()["content"], first.json()["roles"]) == ("", ["live_answers", "code"])
    assert worded.json()["roles"] == ["live_answers", "code"]
    assert every.json() | {"updated_at": None} == {
        "content": "I lead a design team.", "updated_at": None, "roles": "all",
    }  # fmt: skip
    assert none.json()["roles"] == []
    assert (code(unknown), code(some)) == ((422, "validation_error"),) * 2


async def test_the_models_are_the_plan_s_and_unset_roles_read_as_defaults(
    person_bench: PersonBench,
) -> None:
    ids = await catalogue(person_bench)
    plain, frontier = someone(), someone()
    person_bench.plans.frontier.add(frontier[1])

    on_plain = (await person_bench.http.get("/v1/studio/models", headers=bearer(plain))).json()
    on_frontier = await person_bench.http.get("/v1/studio/models", headers=bearer(frontier))

    assert {model["id"] for model in on_plain["models"]} == {ids[FLASH], ids[SMALL]}
    assert ids[SONNET] in {model["id"] for model in on_frontier.json()["models"]}
    assert [(role["role"], role["model_id"], role["max_tokens"]) for role in on_plain["roles"]] == [
        ("live_answers", None, 4_096),
        ("screenshots", None, 4_096),
        ("code", None, 4_096),
        ("system_design", None, 4_096),
        ("notes", None, 8_192),
    ]


async def test_a_role_s_settings_follow_the_plan_the_role_and_the_model(
    person_bench: PersonBench,
) -> None:
    ids = await catalogue(person_bench)
    headers = bearer(someone())

    async def save(role: str, model: str | None, **changes: object) -> httpx.Response:
        body = {"model_id": model, "temperature": 0.7, "max_tokens": 2_000, "reasoning": False}
        return await person_bench.http.put(
            f"/v1/studio/models/roles/{role}", json=body | changes, headers=headers
        )

    off_plan = await save("code", ids[SONNET])
    blind = await save("screenshots", ids[SMALL])
    too_many = await save("code", ids[FLASH], max_tokens=40_000)
    saved = await save("code", ids[FLASH], temperature=0.333, reasoning=True)
    roles = (await person_bench.http.get("/v1/studio/models", headers=headers)).json()["roles"]

    assert code(off_plan) == (422, "model_not_on_plan")
    assert code(blind) == (422, "model_cant_do_role")
    assert blind.json()["error"]["params"]["role"] == "screenshots"
    assert code(too_many) == (422, "max_tokens_range")
    assert too_many.json()["error"]["params"] == {"min": 256, "max": 32_000}
    assert saved.json() == {
        "role": "code", "model_id": ids[FLASH], "temperature": 0.33, "max_tokens": 2_000,
        "reasoning": False,
    }  # fmt: skip
    assert roles[2] == saved.json()


async def test_an_unreadable_plan_is_refused_not_guessed(person_bench: PersonBench) -> None:
    person_bench.plans.unreadable = True

    reply = await person_bench.http.get("/v1/studio/models", headers=bearer(someone()))

    assert code(reply) == (503, "entitlements_unavailable")


async def test_an_uninstalled_skill_leaves_every_prompt_in_one_delivery(
    person_bench: PersonBench,
) -> None:
    home, user_id = person = someone()
    gone, kept = (
        await person_bench.install(person, "gone"),
        await person_bench.install(person, "kept"),
    )
    for name in ("One", "Two"):
        body = {"name": name, "role": "code", "skill_ids": [str(gone), str(kept)]}
        assert (await person_bench.create(person, body)).status_code == 201
    scope = TenancyScope(home, user_id)
    event = SkillRemoved(user_id=user_id, skill_id=gone)

    for _ in range(2):
        async with person_bench.homes.transactions.begin(scope) as session:
            received = ReceivedEvent(event, new_id(), 1, datetime.now(UTC), scope)
            await skill_removed(session, received)
    prompts = (await person_bench.http.get("/v1/studio/prompts", headers=bearer(person))).json()

    assert [prompt["skill_ids"] for prompt in prompts["prompts"]] == [[str(kept)], [str(kept)]]

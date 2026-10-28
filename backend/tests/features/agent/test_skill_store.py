"""The skills store behind Studio's dialog (agent step 15): a skill pinned to the commit its
reference names, found by name for a skills.sh id, kept once per folder and twenty per person,
updated at the default branch, removed by its owner only with `agent.skill.removed` in the
same transaction; a repository scanned, skills.sh
searched softly; GitHub's refusals as the store's codes; the skills read by id for studio."""

import asyncio
import uuid
from datetime import UTC, datetime

from shosai.core.kernel.homes import Home
from shosai.features.agent.infrastructure.person_records import AgentSkillRecord
from shosai.features.identity.contracts import Principal
from tests.features.agent.skills_bench import Repo, SkillsBench, skill_files
from tests.features.billing.people_bench import bearer
from tests.harness.connections import fetch_rows
from tests.harness.run_slot import RunSlot

HOME = Home.EU
SKILLS = "/v1/agent/skills"
OLD, NEW, TAGGED = "a" * 40, "b" * 40, "c" * 40


def kit(bench: SkillsBench) -> None:
    """acme/kit: skills at its head, one more at its tag."""
    head = skill_files("skills/pdf", "skills/docx", "examples/demo", "tools/a/xlsx", "tools/b/xlsx",
                       extra=("skills/pdf/fill.py",))  # fmt: skip
    bench.github.repos["acme/kit"] = Repo(
        refs={"HEAD": OLD, "v1": TAGGED}, files={OLD: head, TAGGED: skill_files("skills/pdf")}
    )


async def test_a_link_s_ref_is_pinned_and_the_skill_kept_whole(skills_bench: SkillsBench) -> None:
    kit(skills_bench)
    who = bearer((HOME, uuid.uuid4()))
    link = "https://github.com/acme/kit/tree/v1/skills/pdf"

    made = await skills_bench.http.post(SKILLS, json={"reference": link}, headers=who)
    listed = await skills_bench.http.get(SKILLS, headers=who)

    assert made.status_code == 201
    skill = made.json()
    assert (skill["reference"], skill["commit"], skill["name"]) == (
        "acme/kit/skills/pdf",
        "ccccccc",
        "pdf",
    )
    assert skill["content"] == "# pdf\nDo pdf."
    assert skill["source_url"] == f"https://github.com/acme/kit/tree/{TAGGED}/skills/pdf"
    assert skill["has_extra_files"] is False
    assert [s["id"] for s in listed.json()["skills"]] == [skill["id"]]


async def test_a_skills_sh_id_is_found_by_name_and_a_wrong_one_explains_itself(
    skills_bench: SkillsBench,
) -> None:
    kit(skills_bench)
    who = bearer((HOME, uuid.uuid4()))
    post = skills_bench.http.post

    found = await post(SKILLS, json={"reference": "https://skills.sh/acme/kit/pdf"}, headers=who)
    answers = [
        await post(SKILLS, json={"reference": ref}, headers=who)
        for ref in ("acme/kit/xlsx", "acme/kit/pptx", "acme/nope/pdf", "acme/kit/../x")
    ]

    assert (found.status_code, found.json()["reference"]) == (201, "acme/kit/skills/pdf")
    assert found.json()["has_extra_files"] is True
    assert [(a.status_code, a.json()["detail"]) for a in answers] == [
        (422, "ambiguous_skill"), (404, "skill_not_found"), (404, "repo_not_found"),
        (422, "skill_reference_invalid"),
    ]  # fmt: skip


async def test_one_row_per_folder_even_when_two_installs_race(skills_bench: SkillsBench) -> None:
    kit(skills_bench)
    who = bearer((HOME, uuid.uuid4()))
    body = {"reference": "acme/kit/skills/docx"}

    answers = await asyncio.gather(
        *(skills_bench.http.post(SKILLS, json=body, headers=who) for _ in range(3))
    )

    assert sorted(a.status_code for a in answers) == [201, 409, 409]
    assert {a.json()["detail"] for a in answers if a.status_code == 409} == {
        "skill_already_installed"
    }


async def test_twenty_skills_a_person_and_no_more(skills_bench: SkillsBench) -> None:
    kit(skills_bench)
    person = uuid.uuid4()
    now = datetime.now(UTC)
    async with skills_bench.homes.transactions.begin(Principal(person, HOME, 0).scope()) as session:
        session.add_all(
            AgentSkillRecord(
                id=uuid.uuid4(), user_id=person, source="github", repo="acme/other",
                skill_path=f"s{n}", ref=OLD, slug=f"s{n}", body="Do.", created_at=now,
                updated_at=now,
            )
            for n in range(20)
        )  # fmt: skip

    full = await skills_bench.http.post(
        SKILLS, json={"reference": "acme/kit/skills/pdf"}, headers=bearer((HOME, person))
    )

    assert (full.status_code, full.json()["detail"]) == (409, "skill_limit_reached")


async def test_an_update_reads_the_default_branch_again(skills_bench: SkillsBench) -> None:
    kit(skills_bench)
    owner = bearer((HOME, uuid.uuid4()))
    body = {"reference": "acme/kit/skills/pdf"}
    made = (await skills_bench.http.post(SKILLS, json=body, headers=owner)).json()
    repo = skills_bench.github.repos["acme/kit"]
    repo.files[NEW] = {"skills/pdf/SKILL.md": "---\nname: pdf\ndescription: v2\n---\nNew way."}
    repo.refs["HEAD"] = NEW

    updated = await skills_bench.http.post(f"{SKILLS}/{made['id']}/update", headers=owner)

    assert updated.status_code == 200
    assert (updated.json()["commit"], updated.json()["content"]) == ("bbbbbbb", "New way.")
    assert updated.json()["id"] == made["id"]


async def test_only_the_owner_removes_a_skill(skills_bench: SkillsBench, run_slot: RunSlot) -> None:
    kit(skills_bench)
    person = uuid.uuid4()
    owner, stranger = bearer((HOME, person)), bearer((HOME, uuid.uuid4()))
    body = {"reference": "acme/kit/skills/pdf"}
    made = (await skills_bench.http.post(SKILLS, json=body, headers=owner)).json()

    not_theirs = await skills_bench.http.delete(f"{SKILLS}/{made['id']}", headers=stranger)
    removed = await skills_bench.http.delete(f"{SKILLS}/{made['id']}", headers=owner)
    again = await skills_bench.http.delete(f"{SKILLS}/{made['id']}", headers=owner)

    assert (not_theirs.status_code, removed.status_code, again.status_code) == (404, 204, 404)
    written = await fetch_rows(
        run_slot.claimed.connections[HOME],
        "SELECT event_type, payload FROM outbox_messages WHERE event_type = 'agent.skill.removed'",
        (),
    )
    payloads = [(row["event_type"], row["payload"]) for row in written]
    assert payloads == [("agent.skill.removed", {"user_id": str(person), "skill_id": made["id"]})]

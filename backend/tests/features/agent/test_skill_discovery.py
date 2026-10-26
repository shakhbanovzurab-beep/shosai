"""Finding skills to install (agent step 15): a repository's skills by name, shallow first and
without examples; skills.sh searched and kept ten minutes, an empty list when it fails; GitHub's
rate limit, a truncated tree and a SKILL.md without front matter as the store's codes; the
person's skills read by id for studio, and nobody else's."""

import uuid

from shosai.core.kernel.homes import Home
from shosai.features.agent.application.installed_skills import InstalledSkills
from shosai.features.identity.contracts import Principal
from tests.features.agent.skills_bench import Repo, SkillsBench, skill_files
from tests.features.billing.people_bench import bearer

HOME = Home.EU
SKILLS = "/v1/agent/skills"
HEAD = "d" * 40


def repo(
    bench: SkillsBench, files: dict[str, str], *, head: str = HEAD, truncated: bool = False
) -> None:
    """acme/kit with the files at its head; a commit is immutable, so new files, a new head."""
    bench.github.repos["acme/kit"] = Repo({"HEAD": head}, {head: files}, truncated)


async def test_a_scan_lists_the_repository_s_skills_by_name(skills_bench: SkillsBench) -> None:
    repo(skills_bench, skill_files("", "skills/pdf", "examples/demo"))
    who = bearer((HOME, uuid.uuid4()))

    scanned = await skills_bench.http.post(
        f"{SKILLS}/scan", json={"repository": "https://github.com/acme/kit"}, headers=who
    )
    wrong = await skills_bench.http.post(f"{SKILLS}/scan", json={"repository": "kit"}, headers=who)

    assert scanned.status_code == 200
    assert [(r["reference"], r["name"], r["description"]) for r in scanned.json()["results"]] == [
        ("acme/kit", "root", "root things"), ("acme/kit/skills/pdf", "pdf", "pdf things"),
    ]  # fmt: skip
    assert (wrong.status_code, wrong.json()["detail"]) == (422, "repository_invalid")


async def test_the_directory_is_searched_kept_and_fails_softly(
    skills_bench: SkillsBench,
) -> None:
    who = bearer((HOME, uuid.uuid4()))
    skills_bench.directory.skills = [
        {
            "id": "acme/kit/pdf",
            "source": "acme/kit",
            "skillId": "pdf",
            "name": "pdf",
            "installs": 7,
        },
        {"name": "no id"},
    ]
    get = skills_bench.http.get

    first = await get(f"{SKILLS}/search", params={"q": "pdf"}, headers=who)
    again = await get(f"{SKILLS}/search", params={"q": "PDF"}, headers=who)
    short = await get(f"{SKILLS}/search", params={"q": "p"}, headers=who)
    skills_bench.directory.failing = True
    failed = await get(f"{SKILLS}/search", params={"q": "docx"}, headers=who)

    assert first.json()["results"] == [
        {"reference": "acme/kit/pdf", "name": "pdf", "description": None, "installs": 7,
         "source_url": "https://skills.sh/acme/kit/pdf"},
    ]  # fmt: skip
    assert again.json() == first.json()
    assert skills_bench.directory.queries == ["pdf", "docx"]
    assert (short.json(), failed.status_code, failed.json()) == (
        {"results": []}, 200, {"results": []},
    )  # fmt: skip


async def test_github_s_refusals_are_the_store_s_codes(skills_bench: SkillsBench) -> None:
    who = bearer((HOME, uuid.uuid4()))
    post = skills_bench.http.post
    repo(skills_bench, {"skills/pdf/SKILL.md": "# no front matter"})
    plain = await post(SKILLS, json={"reference": "acme/kit/skills/pdf"}, headers=who)
    repo(skills_bench, skill_files("skills/pdf"), head="e" * 40, truncated=True)
    huge = await post(SKILLS, json={"reference": "acme/kit/skills/pdf"}, headers=who)
    skills_bench.github.limited = True
    limited = await post(SKILLS, json={"reference": "acme/kit/skills/pdf"}, headers=who)

    assert [(a.status_code, a.json()["detail"]) for a in (plain, huge, limited)] == [
        (422, "no_frontmatter"), (422, "repo_too_large"), (429, "rate_limited"),
    ]  # fmt: skip
    assert int(limited.headers["retry-after"]) >= 1


async def test_studio_reads_only_the_person_s_own_skills(skills_bench: SkillsBench) -> None:
    repo(skills_bench, skill_files("skills/pdf"))
    person, stranger = uuid.uuid4(), uuid.uuid4()
    made = await skills_bench.http.post(
        SKILLS, json={"reference": "acme/kit/skills/pdf"}, headers=bearer((HOME, person))
    )
    skill_id = uuid.UUID(made.json()["id"])

    reader = InstalledSkills()
    async with skills_bench.homes.transactions.begin(
        Principal(person, HOME, 0).scope(), read_only=True
    ) as session:
        own = await reader.skills(session, person, [skill_id, uuid.uuid4()])
        theirs = await reader.skills(session, stranger, [skill_id])

    assert list(own) == [skill_id]
    assert (own[skill_id].repository, own[skill_id].path, own[skill_id].commit) == (
        "acme/kit", "skills/pdf", HEAD,
    )  # fmt: skip
    assert theirs == {}

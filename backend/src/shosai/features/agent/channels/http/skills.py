"""The skills store over HTTP: `/v1/agent/skills*`, behind Studio's skills dialog (ADR 0068
AG-D11; agent step 15).

`GET` lists the person's skills; `POST {reference}` installs one — 201, or 409
`skill_already_installed` / `skill_limit_reached`, 404 `repo_not_found` / `skill_not_found`,
422 `skill_reference_invalid`, `repo_too_large`, `skill_too_large`, `no_frontmatter`,
`skill_file_empty`, `ambiguous_skill`. `POST /{id}/update` reads it again at the default
branch. `DELETE /{id}` removes it (204); `GET /search?q=` searches skills.sh, an empty list
when it does not answer; `POST /scan {repository}` lists a repository's skills. GitHub's rate
limit is 429 `rate_limited` with `Retry-After`, GitHub not answering 502 `github_unavailable`.
"""

from datetime import datetime
from http import HTTPStatus
from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.skill_store import Candidate, SkillStore
from shosai.features.agent.channels.http.shapes import Strict
from shosai.features.agent.infrastructure.person_records import AgentSkillRecord
from shosai.features.identity.contracts import Principal, bearer_principal

SHORT_COMMIT: Final = 7
REFERENCE_MAX: Final = 500
QUERY_MAX: Final = 200


class SkillOut(BaseModel):
    """A SKILL.md-based instruction installed from GitHub, pinned to a commit."""

    id: UUID
    name: str
    description: str
    reference: str = Field(description="owner/repo/path/to/folder — the folder of SKILL.md.")
    commit: str | None = Field(description="The pinned commit, short.")
    source_url: str
    content: str = Field(description="The instructions of SKILL.md, without its front matter.")
    has_extra_files: bool = Field(description="The folder holds other files, which never run.")
    updated_at: datetime


class SkillsOut(BaseModel):
    """The person's skills."""

    skills: list[SkillOut]


class SkillCandidateOut(BaseModel):
    """A skill found in skills.sh or in a repository, not installed yet."""

    reference: str = Field(description="What `POST /v1/agent/skills` takes to install it.")
    name: str
    description: str | None
    installs: int | None
    source_url: str


class SkillSearchOut(BaseModel):
    """Skills to install."""

    results: list[SkillCandidateOut]


class InstallSkillIn(Strict):
    """What to install: a GitHub folder or link, or a skills.sh id or link."""

    reference: str = Field(min_length=1, max_length=REFERENCE_MAX)


class ScanRepositoryIn(Strict):
    """A public GitHub repository, as owner/repo or a link."""

    repository: str = Field(min_length=1, max_length=REFERENCE_MAX)


def skill_out(row: AgentSkillRecord) -> SkillOut:
    """A kept skill as the dialog shows it."""
    return SkillOut(
        id=row.id, name=row.slug, description=row.description,
        reference=f"{row.repo}/{row.skill_path}".rstrip("/"), commit=row.ref[:SHORT_COMMIT],
        source_url=row.source_url, content=row.body, has_extra_files=row.has_extra_files,
        updated_at=row.updated_at,
    )  # fmt: skip


def results_of(found: list[Candidate]) -> SkillSearchOut:
    """Candidates as the dialog lists them."""
    return SkillSearchOut(
        results=[
            SkillCandidateOut(
                reference=c.reference, name=c.name, description=c.description,
                installs=c.installs, source_url=c.source_url,
            )
            for c in found
        ]
    )  # fmt: skip


def build_skills_router(store: SkillStore, ports: PortDirectory) -> APIRouter:
    """The skills store's routes."""
    router = APIRouter(prefix="/v1/agent/skills", tags=["agent"])
    person = Annotated[Principal, Depends(bearer_principal(ports))]

    @router.get("")
    async def list_skills(principal: person) -> SkillsOut:
        """The person's installed skills, the newest first."""
        return SkillsOut(skills=[skill_out(row) for row in await store.listed(principal)])

    @router.post("", status_code=HTTPStatus.CREATED)
    async def install_skill(body: InstallSkillIn, principal: person) -> SkillOut:
        """Install a skill, pinned to the commit its reference names now."""
        return skill_out(await store.install(principal, body.reference))

    @router.post("/{skill_id}/update")
    async def update_skill(skill_id: UUID, principal: person) -> SkillOut:
        """Read the skill again at its repository's default branch."""
        return skill_out(await store.update(principal, skill_id))

    @router.delete("/{skill_id}", status_code=HTTPStatus.NO_CONTENT)
    async def uninstall_skill(skill_id: UUID, principal: person) -> Response:
        """Remove the skill."""
        await store.uninstall(principal, skill_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @router.get("/search")
    async def search_skills(
        principal: person, q: Annotated[str, Query(max_length=QUERY_MAX)] = ""
    ) -> SkillSearchOut:
        """Search the skills.sh directory; fewer than two characters find nothing."""
        return results_of(await store.search(principal, q))

    @router.post("/scan")
    async def scan_repository(body: ScanRepositoryIn, principal: person) -> SkillSearchOut:
        """List the skills of a public GitHub repository, at most 40."""
        return results_of(await store.scan(principal, body.repository))

    return router

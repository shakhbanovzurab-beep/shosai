"""The person's skills store behind Studio's skills dialog (ADR 0068 AG-D11; agent step 15).

A skill is installed from a reference: its repository's commit is pinned — the ref the link
named, else the default branch's head — the skill's folder is found in the tree at that
commit, and its SKILL.md read there. One row per repository and folder is kept by a unique key
with `ON CONFLICT` (the draft checked first and raced), and at most 20 per person, counted under
the person's lock. An update reads the skill again at the default branch's head. Installing,
updating and scanning read GitHub, so they share a limit of 20 a minute per person; a search
reads the directory, 60 a minute. Nothing here gates by plan: no screen states one. The body
is the person's untrusted text: a prompt that carries it wraps it (studio, AG-D11).
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Final
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.web.rate_limit import RateLimitedError
from shosai.features.agent.application.skill_errors import refused
from shosai.features.agent.domain.skill_sources import (
    SkillReference,
    SkillSourceError,
    manifest_of,
    reference_of,
    repository_of,
)
from shosai.features.agent.domain.skill_tree import (
    every_skill_folder,
    has_extra_files,
    previewed_folders,
    resolved_folder,
)
from shosai.features.agent.infrastructure.github_skills import GitHubError, GitHubSkills
from shosai.features.agent.infrastructure.person_records import AgentSkillRecord
from shosai.features.agent.infrastructure.skill_lock import hold_skills_lock
from shosai.features.agent.infrastructure.skills_directory import SkillsDirectory
from shosai.features.identity.contracts import Principal

SKILL = AgentSkillRecord
SKILLS_PER_PERSON: Final = 20
GITHUB_LIMIT: Final = RateLimit("agent.skills_github", 20, timedelta(minutes=1), 10)
SEARCH_LIMIT: Final = RateLimit("agent.skills_search", 60, timedelta(minutes=1), 20)
QUERY_MIN: Final = 2
FILES_AT_ONCE: Final = 8


@dataclass(frozen=True, slots=True)
class Candidate:
    """A skill found in the directory or in a repository, not installed yet."""

    reference: str
    name: str
    description: str | None
    installs: int | None
    source_url: str


@dataclass(frozen=True, slots=True)
class ReadSkill:
    """A skill read from GitHub at a commit, ready to keep."""

    reference: SkillReference
    folder: str
    commit: str
    name: str
    description: str
    body: str
    has_extra_files: bool


def tree_url(repository: str, commit: str, folder: str) -> str:
    """The skill's folder on GitHub, at its pinned commit."""
    return f"https://github.com/{repository}/tree/{commit}" + (f"/{folder}" if folder else "")


class SkillStore:
    """Installs, updates and removes a person's skills, and finds skills to install."""

    def __init__(
        self,
        transactions: HomeTransactions,
        sources: tuple[GitHubSkills, SkillsDirectory, RateLimiter],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._github, self._directory, self._limiter = sources
        self._clock = clock

    async def listed(self, principal: Principal) -> list[AgentSkillRecord]:
        """The person's skills, the newest first."""
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            found = await session.scalars(
                select(SKILL)
                .where(SKILL.user_id == principal.user_id)
                .order_by(SKILL.created_at.desc(), SKILL.id)
            )
            return list(found)

    async def install(self, principal: Principal, raw: str) -> AgentSkillRecord:
        """The skill a reference names, read at its pinned commit and kept."""
        await self._within(principal, GITHUB_LIMIT)
        read = await self._read(reference_of_or_refused(raw), None)
        now = self._clock()
        async with self._transactions.begin(principal.scope()) as session:
            await hold_skills_lock(session, principal.user_id)
            count = await session.scalar(
                select(func.count()).select_from(SKILL).where(SKILL.user_id == principal.user_id)
            )
            if (count or 0) >= SKILLS_PER_PERSON:
                raise AppError("skill_limit_reached", HTTPStatus.CONFLICT)
            kept: AgentSkillRecord | None = await session.scalar(
                insert(SKILL)
                .values(
                    id=new_id(), user_id=principal.user_id, source=read.reference.kind.value,
                    repo=read.reference.repository, skill_path=read.folder, ref=read.commit,
                    slug=read.name, description=read.description, body=read.body,
                    source_url=tree_url(read.reference.repository, read.commit, read.folder),
                    has_extra_files=read.has_extra_files, created_at=now, updated_at=now,
                )
                .on_conflict_do_nothing(constraint="uq_agent_skills_user_repo_path")
                .returning(SKILL)
            )  # fmt: skip
            if kept is None:
                raise AppError("skill_already_installed", HTTPStatus.CONFLICT)
            return kept

    async def update(self, principal: Principal, skill_id: UUID) -> AgentSkillRecord:
        """The skill read again at its repository's default branch."""
        await self._within(principal, GITHUB_LIMIT)
        installed = await self._installed(principal, skill_id)
        reference = reference_of_or_refused(f"{installed.repo}/{installed.skill_path}".rstrip("/"))
        read = await self._read(reference, installed.skill_path)
        async with self._transactions.begin(principal.scope()) as session:
            kept: AgentSkillRecord | None = await session.scalar(
                update(SKILL)
                .where(SKILL.id == skill_id, SKILL.user_id == principal.user_id)
                .values(
                    ref=read.commit, slug=read.name, description=read.description,
                    body=read.body, has_extra_files=read.has_extra_files,
                    source_url=tree_url(installed.repo, read.commit, read.folder),
                    updated_at=self._clock(),
                )
                .returning(SKILL)
            )  # fmt: skip
        if kept is None:
            raise AppError("skill_not_found", HTTPStatus.NOT_FOUND)
        return kept

    async def uninstall(self, principal: Principal, skill_id: UUID) -> None:
        """Remove the person's skill."""
        async with self._transactions.begin(principal.scope()) as session:
            gone = await session.scalar(
                delete(SKILL)
                .where(SKILL.id == skill_id, SKILL.user_id == principal.user_id)
                .returning(SKILL.id)
            )
        if gone is None:
            raise AppError("skill_not_found", HTTPStatus.NOT_FOUND)

    async def search(self, principal: Principal, query: str) -> list[Candidate]:
        """The directory's skills for the query; nothing below two characters."""
        text = query.strip()
        if len(text) < QUERY_MIN:
            return []
        await self._within(principal, SEARCH_LIMIT)
        return [
            Candidate(hit.reference, hit.name, None, hit.installs, hit.source_url)
            for hit in await self._directory.search(text)
        ]

    async def scan(self, principal: Principal, raw: str) -> list[Candidate]:
        """The skills of a repository at its default branch, with their names."""
        await self._within(principal, GITHUB_LIMIT)
        try:
            repository = repository_of(raw)
            commit = await self._github.commit(repository, None)
            folders = previewed_folders(await self._github.tree(repository, commit))
        except (SkillSourceError, GitHubError) as error:
            raise refused(error) from error
        turns = asyncio.Semaphore(FILES_AT_ONCE)

        async def named(folder: str) -> Candidate:
            async with turns:
                try:
                    found = manifest_of(await self._github.skill_file(repository, commit, folder))
                    name, description = found.name, found.description or None
                except SkillSourceError, GitHubError:
                    name, description = "", None
            fallback = folder.rsplit("/", 1)[-1] or repository.rsplit("/", 1)[-1]
            return Candidate(
                f"{repository}/{folder}".rstrip("/"), name or fallback, description, None,
                tree_url(repository, commit, folder),
            )  # fmt: skip

        return list(await asyncio.gather(*(named(folder) for folder in folders)))

    async def _read(self, reference: SkillReference, folder: str | None) -> ReadSkill:
        """The skill at the reference's commit; GitHub's and the file's refusals as codes."""
        try:
            commit = await self._github.commit(reference.repository, reference.ref, fresh=True)
            tree = await self._github.tree(reference.repository, commit)
            folders = every_skill_folder(tree)
            found = folder if folder in folders else resolved_folder(reference, folders)
            manifest = manifest_of(
                await self._github.skill_file(reference.repository, commit, found)
            )
        except (SkillSourceError, GitHubError) as error:
            raise refused(error) from error
        name = manifest.name or found.rsplit("/", 1)[-1] or reference.repository.rsplit("/", 1)[-1]
        return ReadSkill(
            reference, found, commit, name, manifest.description, manifest.body,
            has_extra_files(tree, found),
        )  # fmt: skip

    async def _installed(self, principal: Principal, skill_id: UUID) -> AgentSkillRecord:
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            found = await session.scalar(
                select(SKILL).where(SKILL.id == skill_id, SKILL.user_id == principal.user_id)
            )
        if found is None:
            raise AppError("skill_not_found", HTTPStatus.NOT_FOUND)
        return found

    async def _within(self, principal: Principal, limit: RateLimit) -> None:
        try:
            verdict = await self._limiter.check(limit, str(principal.user_id))
        except REDIS_FAILURES as error:
            raise AppError("skills_unavailable", HTTPStatus.SERVICE_UNAVAILABLE) from error
        if not verdict.allowed:
            raise RateLimitedError(verdict.retry_after)


def reference_of_or_refused(raw: str) -> SkillReference:
    """The reference, or the store's refusal of it."""
    try:
        return reference_of(raw)
    except SkillSourceError as error:
        raise refused(error) from error

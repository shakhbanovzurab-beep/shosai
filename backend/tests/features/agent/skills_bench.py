"""The skills store over HTTP with GitHub and skills.sh played in process (agent step 15).

`FakeGitHub` answers the three calls the store makes — a ref's commit, a tree at a commit, a
file at a commit — from repositories the test writes, and counts them; it can answer with its
rate limit. `FakeDirectory` answers skills.sh's search or fails. The store, its routes and the
people's bearer tokens run over the slot's homes, Valkey and cache.
"""

import json
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from typing import Any, Final
from urllib.parse import unquote, urlsplit

import httpx
import pytest_asyncio
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.cache.metrics import CacheMetrics
from shosai.core.cache.redis_cache import RedisCache
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.skill_store import SkillStore
from shosai.features.agent.channels.http.skills import build_skills_router
from shosai.features.agent.contracts.events import SkillRemoved
from shosai.features.agent.infrastructure.github_skills import GitHubSkills
from shosai.features.agent.infrastructure.skill_metrics import SkillMetrics
from shosai.features.agent.infrastructure.skills_directory import SkillsDirectory
from shosai.features.identity.contracts import AUTHENTICATOR
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.people_bench import BearerOfTheTest
from tests.harness.database_access import DatabaseAccess

SKILL_MD: Final = "---\nname: {name}\ndescription: {name} things\n---\n\n# {name}\nDo {name}.\n"


@dataclass
class Repo:
    """A repository: its refs, and its files at each commit."""

    refs: dict[str, str]
    files: dict[str, dict[str, str]]
    truncated: bool = False


def skill_files(*folders: str, extra: tuple[str, ...] = ()) -> dict[str, str]:
    """SKILL.md in each folder, named after it, and extra files."""
    files = {
        f"{folder}/SKILL.md".lstrip("/"): SKILL_MD.format(name=folder.rsplit("/", 1)[-1] or "root")
        for folder in folders
    }
    return files | dict.fromkeys(extra, "x")


@dataclass
class FakeGitHub:
    """GitHub's API and raw files for the repositories the test writes."""

    repos: dict[str, Repo] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)
    limited: bool = False

    def handle(self, request: httpx.Request) -> httpx.Response:
        """The answer GitHub would give."""
        url = urlsplit(str(request.url))
        self.calls.append(f"{url.hostname}{url.path}")
        if self.limited:
            return httpx.Response(
                403, headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "0"}
            )
        parts = [unquote(part) for part in url.path.split("/") if part]
        if url.hostname == "raw.githubusercontent.com":
            repo = self.repos.get(f"{parts[0]}/{parts[1]}")
            text = repo.files.get(parts[2], {}).get("/".join(parts[3:])) if repo else None
            return httpx.Response(200, text=text) if text is not None else httpx.Response(404)
        repo = self.repos.get(f"{parts[1]}/{parts[2]}")
        if repo is None:
            return httpx.Response(404, json={"message": "Not Found"})
        if parts[3] == "commits":
            sha = repo.refs.get(parts[4])
            return httpx.Response(200, text=sha) if sha else httpx.Response(422)
        tree = [{"path": path, "type": "blob"} for path in repo.files.get(parts[5], {})]
        return httpx.Response(200, json={"tree": tree, "truncated": repo.truncated})


@dataclass
class FakeDirectory:
    """skills.sh's site search."""

    skills: list[Mapping[str, Any]] = field(default_factory=list)
    failing: bool = False
    queries: list[str] = field(default_factory=list)

    def handle(self, request: httpx.Request) -> httpx.Response:
        """The directory's answer, or its failure."""
        self.queries.append(request.url.params.get("q", ""))
        if self.failing:
            return httpx.Response(503)
        return httpx.Response(200, content=json.dumps({"skills": self.skills}).encode())


@dataclass(frozen=True, slots=True)
class SkillsBench:
    """The skills routes and what plays GitHub and skills.sh."""

    http: httpx.AsyncClient
    store: SkillStore
    github: FakeGitHub
    directory: FakeDirectory
    homes: DatabaseAccess


@pytest_asyncio.fixture
async def skills_bench(
    homes: DatabaseAccess, valkey: Redis, redis_cache: Redis
) -> AsyncIterator[SkillsBench]:
    """The store over the slot's homes, with fake GitHub and skills.sh."""
    registry = CollectorRegistry()
    github, directory = FakeGitHub(), FakeDirectory()
    cache = RedisCache(redis_cache, CacheMetrics(registry))
    metrics = SkillMetrics(registry)
    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(github.handle)) as to_github,
        httpx.AsyncClient(transport=httpx.MockTransport(directory.handle)) as to_directory,
    ):
        sources = (
            GitHubSkills(to_github, cache, metrics),
            SkillsDirectory(to_directory, cache, metrics),
            RateLimiter(valkey, KeyValueMetrics(registry)),
        )
        store = SkillStore(homes.transactions, sources, EventOutbox(EventTypes([SkillRemoved])))
        ports = PortDirectory()
        ports.install([AUTHENTICATOR.bind(BearerOfTheTest())])
        app = build_probe_app(extra=(build_skills_router(store, ports),)).app
        async with client_of(app) as http:
            yield SkillsBench(http, store, github, directory, homes)

"""The skills.sh directory, searched for skills to install (ADR 0068 AG-D11; agent step 15).

skills.sh documents `/api/v1/skills/search`, but it answers only a Vercel OIDC token, which an
application outside Vercel cannot hold (checked on 2026-10-26: 401 `authentication_required`).
The directory's own site searches through `/api/search?q=`, public and the draft's source: it
answers `skills[]` of `{id: owner/repo/name, source, skillId, name, installs}`. It is not a
documented contract, so the search fails soft — an empty list, logged and counted — whenever
the answer is late, refused or not of that shape, and a query's answer is kept a minute.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Final

import httpx
import structlog

from shosai.core.cache.port import Cache, CacheKey
from shosai.features.agent.infrastructure.skill_metrics import SkillMetrics, SourceCall

SEARCH: Final = "https://skills.sh/api/search"
SITE: Final = "https://skills.sh"
TIMEOUT: Final = httpx.Timeout(5.0)
RESULTS: Final = 30
ANSWER_BYTES: Final = 1024 * 1024
NAMESPACE: Final = "agent.skills_search.v1"
KEPT_FOR: Final = timedelta(minutes=1)
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class DirectoryHit:
    """A skill the directory lists: its id, name and how many installed it."""

    reference: str
    name: str
    installs: int | None
    source_url: str


def directory_client() -> httpx.AsyncClient:
    """The process's client of skills.sh."""
    return httpx.AsyncClient(timeout=TIMEOUT, limits=httpx.Limits(max_connections=8))


def hits_of(answer: object) -> list[DirectoryHit]:
    """The directory's answer as hits; anything not of its shape is no hit."""
    skills = answer.get("skills") if isinstance(answer, dict) else None
    hits: list[DirectoryHit] = []
    for skill in skills if isinstance(skills, list) else []:
        if not isinstance(skill, dict) or not isinstance(skill.get("id"), str):
            continue
        reference = skill["id"]
        installs = skill.get("installs")
        name = skill.get("name") or skill.get("skillId") or reference.rsplit("/", 1)[-1]
        hits.append(
            DirectoryHit(
                reference=reference, name=str(name),
                installs=installs if isinstance(installs, int) else None,
                source_url=f"{SITE}/{reference}",
            )
        )  # fmt: skip
    return hits[:RESULTS]


class SkillsDirectory:
    """Searches skills.sh, softly."""

    def __init__(self, http: httpx.AsyncClient, cache: Cache, metrics: SkillMetrics) -> None:
        self._http = http
        self._cache = cache
        self._metrics = metrics

    async def search(self, query: str) -> list[DirectoryHit]:
        """The directory's skills for the query; empty when it does not answer."""
        key = CacheKey(NAMESPACE, hashlib.sha256(query.casefold().encode()).hexdigest()[:48])
        kept = await self._cache.get(key)
        if kept is not None:
            return hits_of(json.loads(kept))
        try:
            answer = await self._http.get(SEARCH, params={"q": query})
            answer.raise_for_status()
            if len(answer.content) > ANSWER_BYTES:
                raise ValueError("ответ каталога больше предела")
            found = answer.json()
        except (httpx.HTTPError, ValueError) as error:
            self._metrics.called(SourceCall.SKILLS_SH, "unavailable")
            log.warning("Каталог skills.sh не ответил", error_type=type(error).__name__)
            return []
        self._metrics.called(SourceCall.SKILLS_SH, "ok")
        await self._cache.set(key, json.dumps(found).encode(), KEPT_FOR)
        return hits_of(found)

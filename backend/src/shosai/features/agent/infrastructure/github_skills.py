"""Public GitHub repositories, read for skills (ADR 0068 AG-D11; agent step 15).

One pooled client per process reads three things: the commit a ref points to (the default
branch's head without one), the repository's tree at that commit, and a SKILL.md at that
commit from raw.githubusercontent.com. A commit is immutable, so its tree and its files are
kept in the cache for an hour; a ref's commit for five minutes, for scans — an install or an
update asks for it afresh. The tree and SKILL.md each have
a cap of their own — 8 MiB and 256 KiB, read as a stream and cut off past it (the draft put the
SKILL.md cap on the tree). GitHub's answers become the store's codes: a repository or a ref it
does not know is `repo_not_found` or `skill_not_found`; its rate limit is `rate_limited` with
the seconds to its reset; anything else, or no answer within 10 s, is `github_unavailable`. An
optional token lifts the limit from 60 to 5 000 calls an hour; it is never logged.
"""

import hashlib
import json
import time
from datetime import timedelta
from http import HTTPStatus
from typing import Final
from urllib.parse import quote

import httpx
import structlog

from shosai.core.cache.port import Cache, CacheKey
from shosai.features.agent.domain.skill_sources import SKILL_FILE
from shosai.features.agent.domain.skill_tree import TreeEntry
from shosai.features.agent.infrastructure.skill_metrics import SkillMetrics, SourceCall

API: Final = "https://api.github.com"
RAW: Final = "https://raw.githubusercontent.com"
TIMEOUT: Final = httpx.Timeout(10.0)
TREE_BYTES: Final = 8 * 1024 * 1024
FILE_BYTES: Final = 256 * 1024
NAMESPACE: Final = "agent.skills.v1"
REF_FOR: Final = timedelta(minutes=5)
COMMIT_FOR: Final = timedelta(hours=1)
DEFAULT_REF: Final = "HEAD"
log = structlog.stdlib.get_logger(__name__)


class GitHubError(Exception):
    """GitHub could not give what was asked; `code` is the store's error code."""

    def __init__(self, code: str, retry_after: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.retry_after = retry_after


def github_client(token: str | None) -> httpx.AsyncClient:
    """The process's client of GitHub: a few connections, kept alive, no redirects followed."""
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.AsyncClient(
        headers=headers,
        timeout=TIMEOUT,
        limits=httpx.Limits(max_connections=16, max_keepalive_connections=8),
    )


def cache_key(*parts: str) -> CacheKey:
    """A cache key for parts that may hold any character: their digest."""
    return CacheKey(NAMESPACE, hashlib.sha256("\0".join(parts).encode()).hexdigest()[:48])


class GitHubSkills:
    """Reads commits, trees and SKILL.md files of public repositories."""

    def __init__(self, http: httpx.AsyncClient, cache: Cache, metrics: SkillMetrics) -> None:
        self._http = http
        self._cache = cache
        self._metrics = metrics

    async def commit(self, repository: str, ref: str | None, *, fresh: bool = False) -> str:
        """The commit the ref points to; the default branch's head without one. A scan may take
        it from the cache; an install or an update asks GitHub (`fresh`)."""
        asked = ref or DEFAULT_REF
        key = cache_key("commit", repository, asked)
        kept = None if fresh else await self._cache.get(key)
        if kept is not None:
            return kept.decode()
        url = f"{API}/repos/{repository}/commits/{quote(asked, safe='')}"
        body = await self._read(url, 1024, {"Accept": "application/vnd.github.sha"}, "commit")
        sha = body.decode().strip()
        await self._cache.set(key, sha.encode(), REF_FOR)
        return sha

    async def tree(self, repository: str, commit: str) -> list[TreeEntry]:
        """Every file and folder of the repository at the commit."""
        key = cache_key("tree", repository, commit)
        kept = await self._cache.get(key)
        raw = kept or await self._read(
            f"{API}/repos/{repository}/git/trees/{commit}?recursive=1", TREE_BYTES, {}, "tree"
        )
        found = json.loads(raw)
        if found.get("truncated"):
            raise GitHubError("repo_too_large")
        if kept is None:
            await self._cache.set(key, raw, COMMIT_FOR)
        return [TreeEntry(str(e["path"]), str(e["type"])) for e in found.get("tree", [])]

    async def skill_file(self, repository: str, commit: str, folder: str) -> str:
        """The folder's SKILL.md at the commit."""
        path = f"{folder}/{SKILL_FILE}" if folder else SKILL_FILE
        key = cache_key("file", repository, commit, path)
        kept = await self._cache.get(key)
        url = f"{RAW}/{repository}/{commit}/{quote(path)}"
        raw = kept or await self._read(url, FILE_BYTES, {}, "file")
        if kept is None:
            await self._cache.set(key, raw, COMMIT_FOR)
        return raw.decode("utf-8", errors="replace")

    async def _read(self, url: str, cap: int, headers: dict[str, str], what: str) -> bytes:
        """The answer's body, cut off past its cap; GitHub's refusals as the store's codes."""
        try:
            async with self._http.stream("GET", url, headers=headers) as answer:
                self._refused(answer, what)
                body = bytearray()
                async for piece in answer.aiter_bytes():
                    body += piece
                    if len(body) > cap:
                        self._metrics.called(SourceCall.GITHUB, "too_large")
                        raise GitHubError("repo_too_large" if what == "tree" else "skill_too_large")
        except httpx.HTTPError as error:
            self._metrics.called(SourceCall.GITHUB, "unavailable")
            log.warning("GitHub не ответил", what=what, error_type=type(error).__name__)
            raise GitHubError("github_unavailable") from error
        self._metrics.called(SourceCall.GITHUB, "ok")
        return bytes(body)

    def _refused(self, answer: httpx.Response, what: str) -> None:
        """Raise the store's code for an answer that is not a success."""
        status = answer.status_code
        if status == HTTPStatus.OK:
            return
        remaining = answer.headers.get("x-ratelimit-remaining")
        if status == HTTPStatus.TOO_MANY_REQUESTS or (
            status == HTTPStatus.FORBIDDEN and remaining == "0"
        ):
            self._metrics.called(SourceCall.GITHUB, "rate_limited")
            reset = int(answer.headers.get("x-ratelimit-reset") or 0)
            raise GitHubError("rate_limited", max(reset - int(time.time()), 1) if reset else 60)
        if status in {HTTPStatus.NOT_FOUND, HTTPStatus.UNPROCESSABLE_ENTITY}:
            self._metrics.called(SourceCall.GITHUB, "not_found")
            raise GitHubError("repo_not_found" if what in {"commit", "tree"} else "skill_not_found")
        self._metrics.called(SourceCall.GITHUB, "unavailable")
        log.warning("GitHub отказал", what=what, status=status)
        raise GitHubError("github_unavailable")

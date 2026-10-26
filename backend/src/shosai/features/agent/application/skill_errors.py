"""The skills store's refusals as HTTP answers (agent plan §3.3; step 15).

A reference or a repository that cannot be read as one, or a SKILL.md that is no skill, is
422. What GitHub does not have is 404, and GitHub's rate limit 429 with the seconds to its
reset. GitHub not answering is 502 `github_unavailable`.
"""

from datetime import timedelta
from http import HTTPStatus
from typing import Final

from shosai.core.kernel.errors import AppError
from shosai.core.web.rate_limit import RateLimitedError
from shosai.features.agent.domain.skill_sources import SkillSourceError
from shosai.features.agent.infrastructure.github_skills import GitHubError

RATE_LIMITED: Final = "rate_limited"
DEFAULT_WAIT: Final = timedelta(minutes=1)
STATUSES: Final = {
    "repository_invalid": HTTPStatus.UNPROCESSABLE_ENTITY,
    "skill_reference_invalid": HTTPStatus.UNPROCESSABLE_ENTITY,
    "no_frontmatter": HTTPStatus.UNPROCESSABLE_ENTITY,
    "skill_file_empty": HTTPStatus.UNPROCESSABLE_ENTITY,
    "ambiguous_skill": HTTPStatus.UNPROCESSABLE_ENTITY,
    "repo_too_large": HTTPStatus.UNPROCESSABLE_ENTITY,
    "skill_too_large": HTTPStatus.UNPROCESSABLE_ENTITY,
    "repo_not_found": HTTPStatus.NOT_FOUND,
    "skill_not_found": HTTPStatus.NOT_FOUND,
}


def refused(error: SkillSourceError | GitHubError) -> AppError:
    """The answer for a refusal of the reference, the file or GitHub."""
    if isinstance(error, GitHubError) and error.code == RATE_LIMITED:
        wait = timedelta(seconds=error.retry_after) if error.retry_after else DEFAULT_WAIT
        return RateLimitedError(wait)
    return AppError(error.code, STATUSES.get(error.code, HTTPStatus.BAD_GATEWAY))

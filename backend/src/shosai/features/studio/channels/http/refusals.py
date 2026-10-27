"""Studio's refusals as the platform's error answers (ADR 0008): the rule's code, its status.

A missing thing named by the path is 404, a conflict with what is stored 409, OpenRouter's
list unreadable 503; every other broken rule is 422. The parameters are what the cabinet's
wording needs.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from http import HTTPStatus
from typing import Final

from shosai.core.kernel.errors import AppError
from shosai.features.studio.domain.errors import StudioRule, StudioRuleError

STATUS: Final = {
    StudioRule.PROMPT_NOT_FOUND: HTTPStatus.NOT_FOUND,
    StudioRule.MODEL_NOT_FOUND: HTTPStatus.NOT_FOUND,
    StudioRule.VERSION_NOT_FOUND: HTTPStatus.NOT_FOUND,
    StudioRule.MODEL_ALREADY_LISTED: HTTPStatus.CONFLICT,
    StudioRule.PROMPT_LIMIT_REACHED: HTTPStatus.CONFLICT,
    StudioRule.NO_TIER_PROPOSAL: HTTPStatus.CONFLICT,
    StudioRule.NOTHING_TO_PUBLISH: HTTPStatus.CONFLICT,
    StudioRule.OPENROUTER_UNREACHABLE: HTTPStatus.SERVICE_UNAVAILABLE,
}


def refusal(error: StudioRuleError) -> AppError:
    """The error answer of a broken rule."""
    status = STATUS.get(error.rule, HTTPStatus.UNPROCESSABLE_CONTENT)
    return AppError(error.rule.value, status, params=error.params)


@contextmanager
def refused() -> Iterator[None]:
    """Answer a broken rule of the block with its error."""
    try:
        yield
    except StudioRuleError as error:
        raise refusal(error) from error

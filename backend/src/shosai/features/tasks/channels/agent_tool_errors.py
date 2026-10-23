"""What Leo's task writes share: the person they act for and how a refusal reads to the model.

A refusal of tasks' rules becomes the closed set of tool errors (Leo §8.1). A task, a board,
a column or a workspace the person cannot use is `not_found`. A broken rule is
`invalid_arguments` with its code, and a full board is `limit_reached`. Anything else fails
with its code as the reason, which is an English identifier, never prose.
"""

from typing import Final

from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import ToolError, ToolErrorCode
from shosai.core.kernel.errors import AppError
from shosai.features.identity.contracts import Principal

GONE: Final = frozenset(
    {"task_not_found", "board_not_found", "column_not_found", "workspace_not_found"}
)
BROKEN: Final = frozenset(
    {
        "validation_error", "title_required", "title_too_long", "description_too_long",
        "range_invalid", "recurrence_invalid",
    }
)  # fmt: skip
FULL: Final = frozenset({"board_full"})


def person(context: ToolContext) -> Principal:
    """The person the run acts for; a tool context always carries one."""
    user_id = context.scope.user_id
    if user_id is None:
        message = "контекст инструмента без человека"
        raise ValueError(message)
    return Principal(user_id, context.scope.home, 0)


def tool_error(error: AppError) -> ToolError:
    """A refusal of tasks as a tool error the model can explain."""
    if error.code in GONE:
        return ToolError(ToolErrorCode.NOT_FOUND)
    if error.code in BROKEN:
        return ToolError(ToolErrorCode.INVALID_ARGUMENTS, {"reason": error.code})
    if error.code in FULL:
        return ToolError(ToolErrorCode.LIMIT_REACHED, {"reason": error.code})
    return ToolError(ToolErrorCode.FAILED, {"reason": error.code})

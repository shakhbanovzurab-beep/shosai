"""Leo's `tasks` toolset: what the model may call over the person's tasks (tasks step 7).

Two reads (Leo §8.1): `tasks.search` finds the tasks the person may read by words, status,
due window, space, meeting, board and whether they do them; `tasks.list_board` reads one of
their boards as they see it. Their results carry text the person may not have written — a
colleague's, a meeting's through extraction, a Jira user's — so both are labelled
`task:foreign` (TK-D9, Leo §7.4). Plan, fact and the stopwatch are read, never changed
(KT-D8). The writes come with step 8.
"""

from datetime import timedelta
from typing import Final

from shosai.core.agent_tools.spec import Provenance, ToolEffect, ToolSpec
from shosai.features.tasks.channels.agent_tool_models import (
    BoardRead,
    FoundTasks,
    ListBoard,
    SearchTasks,
)

TOOLSET: Final = "tasks"
SEARCH_BUDGET: Final = 4_000
BOARD_BUDGET: Final = 6_000

SEARCH_TASKS: Final = ToolSpec(
    name="tasks.search", toolset=TOOLSET,
    description=(
        "Find tasks the user may read: their own, their workspaces' and those from meetings."
        " Filter by words of the title, status, due window in the user's day, workspace, the"
        " user's personal tasks, a meeting, a board, or what the user does. Results include"
        " where the user's card sits and the task's plan, fact and stopwatch, read only."
    ),
    input=SearchTasks, output=FoundTasks, effect=ToolEffect.READ,
    result_budget=SEARCH_BUDGET, timeout=timedelta(seconds=5),
    provenance=Provenance.TASK_FOREIGN,
)  # fmt: skip
LIST_BOARD: Final = ToolSpec(
    name="tasks.list_board", toolset=TOOLSET,
    description=(
        "Read one of the user's Kanban boards as they see it: its columns left to right with"
        " their first cards, top first, and how many more each holds; also the user's other"
        " boards. Without a board id it reads the board incoming work lands on."
    ),
    input=ListBoard, output=BoardRead, effect=ToolEffect.READ,
    result_budget=BOARD_BUDGET, timeout=timedelta(seconds=5),
    provenance=Provenance.TASK_FOREIGN,
)  # fmt: skip
READ_TOOLS: Final = (SEARCH_TASKS, LIST_BOARD)

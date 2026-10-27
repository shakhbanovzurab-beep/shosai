"""The tasks slice as composition sees it (tasks plan §3.1).

Step 1 published the contract, the events and the domain; step 2 added the tables in each
home, the shareable `task` with its parent and named-reader rules (TK-D2), and the handler
of a person's data; step 3a the one task API (`/v1/tasks*`) and the task reader, step 3b
a task's checklist and comments, step 3c its attachments and cover through files' held
objects, step 4 boards with their columns and cards, and step 4s stickers and values. Time, the
action items from meetings, Leo's tools and Jira join in later steps.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.core.idempotency.action_items import ActionItems
from shosai.features.tasks.application.account_data import ACCOUNT_DATA, TasksAccountData
from shosai.features.tasks.application.attachment_releases import AttachmentReleases
from shosai.features.tasks.application.attachments import Attachments
from shosai.features.tasks.application.board_facts import BoardFactsReader
from shosai.features.tasks.application.board_reads import BoardReads
from shosai.features.tasks.application.board_stickers import BoardStickers
from shosai.features.tasks.application.boards import BoardWrites
from shosai.features.tasks.application.cards import Cards
from shosai.features.tasks.application.clocks import Clocks
from shosai.features.tasks.application.columns import Columns
from shosai.features.tasks.application.comments import Comments
from shosai.features.tasks.application.leo_reads import LeoReads
from shosai.features.tasks.application.stickers import Stickers
from shosai.features.tasks.application.subtasks import Subtasks
from shosai.features.tasks.application.task_edits import TaskEdits
from shosai.features.tasks.application.task_reads import TaskReads
from shosai.features.tasks.application.task_writes import TaskWrites
from shosai.features.tasks.application.values import Values
from shosai.features.tasks.channels.agent_board_specs import BOARD_TOOLS
from shosai.features.tasks.channels.agent_board_tools import BoardTools
from shosai.features.tasks.channels.agent_board_work import BoardWork
from shosai.features.tasks.channels.agent_column_tools import ColumnTools
from shosai.features.tasks.channels.agent_task_changes import TaskChanges
from shosai.features.tasks.channels.agent_task_creates import TaskCreates
from shosai.features.tasks.channels.agent_tool_reads import agent_tools
from shosai.features.tasks.channels.agent_tools import READ_TOOLS
from shosai.features.tasks.channels.agent_write_tools import WRITE_TOOLS
from shosai.features.tasks.channels.http.attachments import build_attachments_router
from shosai.features.tasks.channels.http.board_parts import build_board_parts_router
from shosai.features.tasks.channels.http.boards import build_boards_router
from shosai.features.tasks.channels.http.clocks import build_clocks_router
from shosai.features.tasks.channels.http.stickers import (
    build_stickers_router,
    build_values_router,
)
from shosai.features.tasks.channels.http.tasks import build_tasks_router
from shosai.features.tasks.channels.http.threads import build_threads_router
from shosai.features.tasks.channels.subscriptions import subscriptions
from shosai.features.tasks.channels.tasks import PERIODIC_JOBS, task_handlers
from shosai.features.tasks.contracts import BOARD_READER, TASK_READER
from shosai.features.tasks.contracts.events import (
    TaskAssigned,
    TaskCompleted,
    TaskDeleted,
    TaskDueChanged,
    TaskReopened,
)
from shosai.features.tasks.infrastructure.attachment_records import (
    TaskAttachmentRecord,
    TaskAttachmentReleaseRecord,
)
from shosai.features.tasks.infrastructure.board_records import (
    BoardColumnRecord,
    BoardRecord,
    TaskPlacementRecord,
    TaskSettingsRecord,
)
from shosai.features.tasks.infrastructure.clock_records import TaskClockSpanRecord
from shosai.features.tasks.infrastructure.sticker_records import (
    BoardStickerRecord,
    StickerRecord,
    StickerStateRecord,
    TaskStickerValueRecord,
)
from shosai.features.tasks.infrastructure.task_records import (
    TASK_RESOURCE,
    MeetingTaskSetRecord,
    TaskRecord,
)
from shosai.features.tasks.infrastructure.thread_records import (
    TaskCommentRecord,
    TaskSubtaskRecord,
)


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """Bind the routes of tasks, the task reader and the handler of a person's data."""
    transactions, ports = services.transactions, services.ports
    reads = TaskReads(transactions, ports)
    writes = TaskWrites(transactions, ports, (services.outbox, services.effects))
    edits = TaskEdits(transactions, ports, services.outbox)
    threads = (Subtasks(transactions, ports), Comments(transactions, ports, services.effects))
    boards = (BoardReads(transactions, ports), BoardWrites(transactions, ports, services.outbox))
    items = ActionItems(services.effects, services.outbox)
    releases = AttachmentReleases(transactions, ports)
    board_work = BoardWork(transactions, items, services.outbox)
    yield FeatureParts(
        http_routers=(
            build_tasks_router((reads, writes, edits), ports),
            build_threads_router(threads, ports),
            build_attachments_router(Attachments(transactions, ports), ports),
            build_boards_router(boards, ports),
            build_board_parts_router(
                (Columns(transactions), Cards(transactions, ports, (writes, edits))), ports
            ),
            build_stickers_router((Stickers(transactions), BoardStickers(transactions)), ports),
            build_values_router(Values(transactions, ports), ports),
            build_clocks_router(Clocks(transactions, ports), ports),
        ),
        task_handlers=task_handlers(releases),
        subscriptions=subscriptions(ports),
        agent_tools=(
            *agent_tools(LeoReads(transactions, ports)),
            TaskCreates(transactions, (writes, items)).bound(),
            *TaskChanges(transactions, ports, (edits, items)).bound(),
            *BoardTools(board_work, (boards[0], ports, releases)).bound(),
            *ColumnTools(board_work).bound(),
        ),
        periodic_jobs=PERIODIC_JOBS,
        provides=(
            ACCOUNT_DATA_HANDLERS.bind(TasksAccountData(transactions, ports)),
            TASK_READER.bind(reads),
            BOARD_READER.bind(BoardFactsReader()),
        ),
    )


TASKS = FeatureModule(
    name="tasks",
    build=build,
    models=(
        TaskRecord,
        TaskSubtaskRecord,
        TaskCommentRecord,
        TaskAttachmentRecord,
        TaskAttachmentReleaseRecord,
        MeetingTaskSetRecord,
        BoardRecord,
        BoardColumnRecord,
        TaskPlacementRecord,
        TaskSettingsRecord,
        StickerRecord,
        StickerStateRecord,
        BoardStickerRecord,
        TaskStickerValueRecord,
        TaskClockSpanRecord,
    ),
    events=(TaskAssigned, TaskDueChanged, TaskCompleted, TaskReopened, TaskDeleted),
    account_data=(ACCOUNT_DATA,),
    shareable=(TASK_RESOURCE,),
    agent_tools=(*READ_TOOLS, *WRITE_TOOLS, *BOARD_TOOLS),
)

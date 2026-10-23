"""A task from a team chat answers as the mocks' `chat-source` test, and only the server's
path makes one (TK-D13, tasks plan §3.10)."""

import re
import uuid
from datetime import UTC, datetime

import pytest
from prometheus_client import CollectorRegistry
from psycopg import errors

from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.contracts import Principal
from shosai.features.tasks.application.task_writes import NewTask, TaskWrites
from shosai.features.tasks.contracts import ChatOrigin, Messenger
from shosai.features.tasks.domain.tasks import Assignee
from tests.features.tasks.board_helpers import board, code_of, column_ids, made
from tests.features.tasks.task_bench import HOME, OUTBOX, TaskBench

SENT = datetime(2026, 10, 20, 13, tzinfo=UTC)
RELEASE = ChatOrigin(
    uuid.uuid4(), Messenger.TELEGRAM, "  Release team ", "https://t.me/c/2093847561/8815", SENT
)
CHAT_ROW = (
    "INSERT INTO tasks (id, user_id, org_id, access, title, source, created_by,"
    " source_chat_messenger, source_chat_title, source_chat_message_at)"
    " VALUES (%s, %s, %s, %s, 'Из чата', %s, %s, %s, %s, now())"
)


async def made_from_chat(
    bench: TaskBench, who: uuid.UUID, org: uuid.UUID, chat: ChatOrigin | None = RELEASE
) -> uuid.UUID:
    """A workspace's task made on the server's path from a chat's message."""
    writes = TaskWrites(
        bench.homes.transactions,
        bench.ports,
        (OUTBOX, EffectLedger(EffectKeyMetrics(CollectorRegistry()))),
    )
    draft = NewTask(
        title="Update the release checklist", workspace_id=org, assignee=Assignee(user_id=who),
        chat=chat,
    )  # fmt: skip
    async with bench.homes.transactions.begin(TenancyScope(HOME, who, org)) as session:
        return await writes.make(session, Principal(who, HOME, 0), draft)


async def test_a_chat_task_shows_its_chat_on_the_card_and_its_message_in_the_panel(
    task_bench: TaskBench,
) -> None:
    me, org = uuid.uuid4(), uuid.uuid4()
    await task_bench.workspace(org, me)
    board_id = await made(task_bench, me)
    todo = uuid.UUID(column_ids(await board(task_bench, me, board_id))[0])
    from_chat, by_hand = await made_from_chat(task_bench, me, org), await task_bench.task(me)
    for task in (from_chat, by_hand):
        await task_bench.place_in(me, task, (uuid.UUID(board_id), todo))

    cards = {c["id"]: c for c in (await board(task_bench, me, board_id))["columns"][0]["cards"]}
    detail = (await task_bench.call(me, "GET", f"/v1/tasks/{from_chat}")).json()

    assert cards[str(from_chat)]["source_chat"] == {
        "messenger": "telegram",
        "chat_title": "Release team",
    }
    assert cards[str(by_hand)]["source_chat"] is None
    assert detail["source"]["kind"] == "chat"
    assert detail["source"]["chat"] == {
        "connection_id": str(RELEASE.connection_id), "messenger": "telegram",
        "chat_title": "Release team",
        "message": {"url": RELEASE.message_url, "sent_at": "2026-10-20T13:00:00Z"},
    }  # fmt: skip
    assert re.fullmatch(r"https://t\.me/c/\d+/\d+", detail["source"]["chat"]["message"]["url"])
    assert detail["space"]["workspace_id"] == str(org)


async def test_a_request_never_names_a_chat_source(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    board_id = await made(task_bench, me)
    todo = column_ids(await board(task_bench, me, board_id))[0]
    source = {"kind": "chat", "chat": {"messenger": "telegram", "chat_title": "Release team"}}

    task = await task_bench.call(
        me, "POST", "/v1/tasks", {"title": "Чужой источник", "source": source}
    )
    card = await task_bench.call(
        me, "POST", f"/v1/boards/{board_id}/cards",
        {"title": "Карточка", "column_id": todo, "position": 0, "source": source},
    )  # fmt: skip

    assert [(a.status_code, code_of(a)) for a in (task, card)] == [(422, "validation_error")] * 2


async def test_only_a_workspaces_task_comes_from_a_chat(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    writes = TaskWrites(
        task_bench.homes.transactions, task_bench.ports,
        (OUTBOX, EffectLedger(EffectKeyMetrics(CollectorRegistry()))),
    )  # fmt: skip

    async with task_bench.homes.transactions.begin(TenancyScope(HOME, me)) as session:
        with pytest.raises(AppError) as refused:
            await writes.make(session, Principal(me, HOME, 0), NewTask(title="Лично", chat=RELEASE))

    assert refused.value.code == "validation_error"


# Источник, автор, мессенджер, имя чата и пространство строки задачи.
type ChatRow = tuple[str, str, str | None, str | None, bool]
PARTIAL: list[ChatRow] = [
    ("chat", "leo", "telegram", None, True),
    ("chat", "leo", None, "Release team", True),
    ("chat", "person", "telegram", "Release team", True),
    ("chat", "leo", "telegram", "Release team", False),
    ("manual", "person", "telegram", "Release team", True),
    ("chat", "leo", "whatsapp", "Release team", True),
]


@pytest.mark.parametrize("row", PARTIAL)
async def test_the_database_refuses_a_partial_chat_source(
    task_bench: TaskBench, row: ChatRow
) -> None:
    me, org = uuid.uuid4(), uuid.uuid4()
    source, created_by, messenger, title, workspace = row
    space = (org, "organization") if workspace else (None, None)

    with pytest.raises(errors.CheckViolation):
        await task_bench.connection.execute(
            CHAT_ROW, (uuid.uuid4(), me, *space, source, created_by, messenger, title)
        )

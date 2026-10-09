"""A task runs in the data home its payload names (target architecture §4.1 rule 3)."""

import uuid
from datetime import timedelta

import pytest
import sqlalchemy as sa
from redis.asyncio import Redis

from shosai.core.kernel.homes import Home
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler
from shosai.core.tasks.queues import TaskQueue
from tests.core.observability.capture import captured_logs
from tests.core.tasks.workbench import HomeProbe, eventually, running, settled, workbench
from tests.harness.connections import fetch_value
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

OTHER_HOME = {Home.RU: Home.EU, Home.EU: Home.RU}
WRITE_NOTE = TaskDeclaration(
    name="probe.write_note",
    queue=TaskQueue.DEFAULT,
    payload=HomeProbe,
    deadline=timedelta(seconds=10),
    retry=NO_RETRY,
)


def note_writer(homes: DatabaseAccess, table: sa.TableClause) -> TaskHandler[HomeProbe]:
    """A handler writing one row in the transaction of the payload's scope."""

    async def write_note(payload: HomeProbe) -> None:
        async with homes.transactions.begin(payload.scope()) as session:
            await session.execute(
                sa.insert(table).values(id=payload.record_id, org_id=None, note=payload.home)
            )

    return TaskHandler(WRITE_NOTE, write_note)


@pytest.mark.parametrize("home", list(Home))
async def test_a_task_writes_only_into_the_home_named_by_its_payload(
    valkey: Redis,
    homes: DatabaseAccess,
    probe_table: sa.TableClause,
    run_slot: RunSlot,
    home: Home,
) -> None:
    bench = workbench(valkey, [note_writer(homes, probe_table)])
    record_id = uuid.uuid4()

    with captured_logs() as logs:
        async with running(bench.broker()):
            await bench.system.sender.send(WRITE_NOTE, HomeProbe(home=home, record_id=record_id))
            await eventually(settled(bench, WRITE_NOTE.name, "succeeded"))

    stored_in = {
        server: await fetch_value(
            connection, "SELECT count(*) FROM probe_records WHERE id = %s", (record_id,)
        )
        for server, connection in run_slot.claimed.connections.items()
    }
    assert stored_in == {home: 1, OTHER_HOME[home]: 0}
    [line] = [line for line in logs.lines() if line["message"] == "Задача выполнена"]
    assert line["home"] == home.value
    assert line["task_name"] == WRITE_NOTE.name

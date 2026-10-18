"""`FileReader` (files step 9): through `visible_files`, a deleted file and a file of an
account in its deletion window are neither in `facts` nor opened — for the owner and for a
workspace member through a share — and a file shared with the viewer is.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from shosai.core.kernel.homes import Home
from shosai.features.files.contracts import FileUnreadableError
from shosai.features.identity.contracts import AccountDeletionScheduled, Principal
from shosai.features.workspaces.contracts import Viewer
from tests.features.files.file_bench import FileBench
from tests.features.files.test_account_window import deliver, shared_file
from tests.features.files.upload_bench import person
from tests.harness.run_slot import RunSlot

BODY = b"plan " * 2_000


async def readable(bench: FileBench, who: Principal, file_id: uuid.UUID) -> tuple[bool, bytes]:
    """Whether `facts` names the file for `who`, and the bytes `open` gives them."""
    viewer = Viewer(who.user_id)
    async with bench.uploads.transactions.begin(who.scope(), read_only=True) as session:
        facts = await bench.reader.facts(session, viewer, [file_id])
    try:
        async with bench.reader.open(who.home, viewer, file_id) as stream:
            body = b"".join([chunk async for chunk in stream.chunks(64 * 1024)])
    except FileUnreadableError:
        body = b""
    return file_id in facts, body


async def test_the_reader_serves_what_the_viewer_may_read_and_nothing_hidden(
    file_bench: FileBench, run_slot: RunSlot
) -> None:
    owner, member = person(Home.RU, uuid.uuid4()), person(Home.RU, uuid.uuid4())
    stranger = person(Home.RU, uuid.uuid4())
    file_id = await shared_file(file_bench, run_slot, owner, member)
    key = f"u/{owner.user_id}/f/{file_id}"
    await file_bench.uploads.objects[Home.RU].put(key, BODY, content_type="text/plain")

    shown = [await readable(file_bench, who, file_id) for who in (owner, member, stranger)]
    await file_bench.manager.delete(owner, file_id)
    deleted = [await readable(file_bench, who, file_id) for who in (owner, member)]
    await file_bench.support.restore(Home.RU, owner.user_id, file_id)
    start = datetime.now(UTC)
    scheduled = AccountDeletionScheduled(user_id=owner.user_id, erase_at=start + timedelta(days=7))
    await deliver(file_bench, owner, scheduled, start)
    in_window = [await readable(file_bench, who, file_id) for who in (owner, member)]

    assert shown == [(True, BODY), (True, BODY), (False, b"")]
    assert deleted == [(False, b""), (False, b"")]
    assert in_window == [(False, b""), (False, b"")]


async def test_facts_of_no_files_is_empty_and_a_missing_file_does_not_open(
    file_bench: FileBench,
) -> None:
    who = person(Home.EU, uuid.uuid4())
    viewer = Viewer(who.user_id)

    async with file_bench.uploads.transactions.begin(who.scope(), read_only=True) as session:
        assert await file_bench.reader.facts(session, viewer, []) == {}
    with pytest.raises(FileUnreadableError):
        async with file_bench.reader.open(Home.EU, viewer, uuid.uuid4()):
            pass

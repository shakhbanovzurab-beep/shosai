"""The live transcript's store, the socket's binding and the sweeps (notes step 4)."""

import uuid
from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.notes.contracts import LiveLine, MeetingNotFoundError, Side
from shosai.features.notes.domain.meetings import MAX_LENGTH, EndCause
from shosai.features.notes.infrastructure.meeting_records import MeetingRecord
from shosai.features.notes.infrastructure.run_records import RunRecord
from tests.features.notes.meeting_bench import MeetingBench


async def meeting(
    bench: MeetingBench, person: uuid.UUID, started_at: datetime, **fields: object
) -> uuid.UUID:
    """A live meeting of the person; its id."""
    meeting_id = uuid.uuid4()
    async with bench.homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
        session.add(
            MeetingRecord(
                id=meeting_id, user_id=person, title="Созвон", started_at=started_at, **fields
            )
        )
    return meeting_id


def line(meeting_id: uuid.UUID, seq: int, at: datetime, text: str = "Да.") -> LiveLine:
    """A live phrase of the meeting, as capture queues it."""
    return LiveLine(meeting_id, seq, at, 700, Side.THEM if seq % 2 else Side.ME, text)


async def stored(bench: MeetingBench, meeting_id: uuid.UUID) -> MeetingRecord:
    """The meeting as stored now."""
    async with bench.homes.transactions.begin(TenancyScope(Home.RU), read_only=True) as session:
        record = await session.get(MeetingRecord, meeting_id)
    assert record is not None
    return record


async def test_a_replayed_batch_stores_nothing_new_and_equal_texts_are_two_lines(
    meeting_bench: MeetingBench,
) -> None:
    person, now = uuid.uuid4(), meeting_bench.clock()
    kept = await meeting(meeting_bench, person, now)
    not_kept = await meeting(meeting_bench, person, now, kept=False)
    batch = [
        line(kept, 1, now),
        line(kept, 2, now + timedelta(seconds=1)),
        line(kept, 3, now + timedelta(seconds=2), "я" * 2500),
        line(not_kept, 1, now),
        line(uuid.uuid4(), 1, now),
    ]

    first = await meeting_bench.transcript.append(Home.RU, batch)
    again = await meeting_bench.transcript.append(Home.RU, batch)
    async with meeting_bench.homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
        tail = await meeting_bench.transcript.tail(session, kept, 2)

    assert (first.stored, first.replayed, first.refused) == (3, 0, 2)
    assert (again.stored, again.replayed, again.refused) == (0, 3, 2)
    assert [(item.seq, item.speaker) for item in tail] == [(2, 0), (3, 1)]
    assert len(tail[-1].text) == 2000


async def test_a_socket_binds_only_the_persons_active_meeting(meeting_bench: MeetingBench) -> None:
    person, now = uuid.uuid4(), meeting_bench.clock()
    live = await meeting(meeting_bench, person, now)
    ended = await meeting(
        meeting_bench, person, now, status="completed", ended_at=now + timedelta(minutes=1)
    )

    async with meeting_bench.homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
        bound = await meeting_bench.binder.bind(session, person, live)
        for other, who in ((ended, person), (live, uuid.uuid4())):
            with pytest.raises(MeetingNotFoundError):
                await meeting_bench.binder.bind(session, who, other)

    assert (bound.meeting_id, bound.kept, bound.ends_by) == (live, True, now + MAX_LENGTH)


async def test_the_sweep_ends_silence_after_the_last_audio_and_every_meeting_at_six_hours(
    meeting_bench: MeetingBench,
) -> None:
    person, now = uuid.uuid4(), meeting_bench.clock()
    stopped = await meeting(meeting_bench, person, now - timedelta(minutes=40))
    pausing = await meeting(meeting_bench, person, now - timedelta(hours=2))
    endless = await meeting(meeting_bench, person, now - MAX_LENGTH - timedelta(minutes=2))
    quiet = await meeting(meeting_bench, person, now - timedelta(minutes=30))
    await meeting_bench.transcript.append(
        Home.RU,
        [
            line(pausing, 1, now - timedelta(hours=1, minutes=10)),
            line(quiet, 1, now - timedelta(minutes=9)),
        ],
    )
    meeting_bench.signal.audio.update(
        {
            stopped: now - timedelta(minutes=6),
            pausing: now - timedelta(seconds=10),
            endless: now - timedelta(seconds=5),
        }
    )

    async with meeting_bench.sweeps() as sweeps:
        ended = await sweeps.end_forgotten(Home.RU)

    assert ended == 3
    assert (await stored(meeting_bench, stopped)).ended_at == now - timedelta(minutes=6)
    assert (await stored(meeting_bench, pausing)).status == "active"
    assert (await stored(meeting_bench, endless)).ended_at == (
        now - MAX_LENGTH - timedelta(minutes=2) + MAX_LENGTH
    )
    quiet_end = (await stored(meeting_bench, quiet)).ended_at
    assert quiet_end == now - timedelta(minutes=9) + timedelta(milliseconds=700)


async def test_the_settle_sweep_gives_a_late_spoken_meeting_its_run_and_counts_lost_lines(
    meeting_bench: MeetingBench,
) -> None:
    person, now = uuid.uuid4(), meeting_bench.clock()
    late = await meeting(meeting_bench, person, now - timedelta(minutes=20))
    await meeting_bench.lifecycle.close_swept(
        TenancyScope(Home.RU, person), late, EndCause.CLIENT, now
    )
    await meeting_bench.transcript.append(
        Home.RU,
        [
            line(late, seq, now - timedelta(minutes=15) + timedelta(seconds=seq))
            for seq in (1, 2, 4)
        ],
    )
    meeting_bench.signal.shown[late] = 5
    meeting_bench.clock.advance(timedelta(minutes=2))

    async with meeting_bench.sweeps() as sweeps:
        first = await sweeps.settle(Home.RU)
        again = await sweeps.settle(Home.RU)
        await meeting_bench.transcript.append(Home.RU, [line(late, 5, now)])
        unsettled = (await stored(meeting_bench, late)).settled_at
        third = await sweeps.settle(Home.RU)
    async with meeting_bench.homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
        runs = (await session.scalars(sa.select(RunRecord.source))).all()

    assert (first, again) == (1, 0)
    assert runs == ["live"]
    assert (
        meeting_bench.registry.get_sample_value("shosai_notes_transcript_lines_missing_total") == 2
    )
    assert unsettled is None
    assert third == 1
    assert (await stored(meeting_bench, late)).line_count == 4

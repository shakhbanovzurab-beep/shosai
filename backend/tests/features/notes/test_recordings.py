"""A recording before it is transcribed: the rules and the bounded tools (step 9a, MT-D10)."""

import asyncio
import stat
from itertools import pairwise
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.notes.domain.recordings import (
    PART_MAX_MS,
    PART_MIN_MS,
    RECORDING_MAX_MS,
    MediaFacts,
    Part,
    parts_of,
    readable,
    too_long,
)
from shosai.features.notes.infrastructure.media_tools import (
    UNREADABLE,
    MediaError,
    MediaLimits,
    MediaTools,
)
from tests.features.notes.recording_bench import LIMITS, VIDEO_SECONDS


@given(
    st.integers(min_value=1, max_value=RECORDING_MAX_MS),
    st.lists(st.integers(min_value=0, max_value=RECORDING_MAX_MS), max_size=200),
)
def test_parts_cover_the_recording_in_order_none_over_ninety_minutes(
    duration_ms: int, silences: list[int]
) -> None:
    parts = parts_of(duration_ms, silences)

    assert parts[0].start_ms == 0
    assert parts[-1].end_ms == duration_ms
    for before, after in pairwise(parts):
        assert before.end_ms == after.start_ms
        assert PART_MIN_MS <= before.duration_ms <= PART_MAX_MS
    assert parts[-1].duration_ms <= PART_MAX_MS


def test_a_part_ends_in_the_latest_pause_of_its_ninety_minutes() -> None:
    minute = 60_000
    assert parts_of(100 * minute, [30 * minute, 85 * minute, 91 * minute]) == [
        Part(0, 85 * minute), Part(85 * minute, 100 * minute),
    ]  # fmt: skip
    assert parts_of(200 * minute, []) == [
        Part(0, 90 * minute), Part(90 * minute, 180 * minute), Part(180 * minute, 200 * minute),
    ]  # fmt: skip
    assert parts_of(90 * minute, []) == [Part(0, 90 * minute)]
    assert parts_of(0, [5]) == []


def test_a_part_is_heard_a_minute_past_each_cut_within_the_recording() -> None:
    minute = 60_000
    assert Part(0, 90 * minute).heard(200 * minute) == Part(0, 91 * minute)
    assert Part(90 * minute, 180 * minute).heard(200 * minute) == Part(89 * minute, 181 * minute)
    assert Part(180 * minute, 200 * minute).heard(200 * minute) == Part(179 * minute, 200 * minute)


def test_only_allowed_containers_and_codecs_are_read_and_six_hours_is_the_most() -> None:
    assert readable(MediaFacts(("mov", "mp4", "m4a"), "aac", 1000))
    assert readable(MediaFacts(("matroska", "webm"), "opus", 1000))
    assert not readable(MediaFacts(("gif",), None, 0))
    assert not readable(MediaFacts(("avi",), "mp3", 1000))
    assert not readable(MediaFacts(("mp4",), "ac3", 1000))
    assert not too_long(RECORDING_MAX_MS)
    assert too_long(RECORDING_MAX_MS + 1)


async def test_the_tools_read_a_video_find_its_pauses_and_cut_a_part(
    video: Path, tmp_path: Path
) -> None:
    tools = MediaTools(LIMITS)

    facts = await tools.probe(video)
    pauses = await tools.silences(video)
    part = await tools.cut(video, Part(0, 60_000), tmp_path / "part.ogg")
    cut = await tools.probe(part)

    assert readable(facts)
    assert abs(facts.duration_ms - VIDEO_SECONDS * 1000) < 500
    assert len(pauses) >= 10
    assert all(abs(moment % 30_000 - 27_000) < 1_500 for moment in pauses)
    assert (cut.containers, cut.audio_codec) == (("ogg",), "opus")
    assert abs(cut.duration_ms - 60_000) < 200


async def probed(tools: MediaTools, path: Path) -> MediaFacts | str:
    """What the header says, or the code of the probe's failure."""
    try:
        return await tools.probe(path)
    except MediaError as error:
        return error.code


async def test_a_picture_or_garbage_is_refused_from_its_header(tmp_path: Path) -> None:
    picture = tmp_path / "frame.gif"
    process = await asyncio.create_subprocess_exec(
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=32x32", "-frames:v", "1",
        str(picture),
    )  # fmt: skip
    assert await process.wait() == 0
    garbage = tmp_path / "meeting.mp4"
    garbage.write_bytes(b"\x00\x01hostile" * 4096)
    tools = MediaTools(LIMITS)

    hostile = await probed(tools, garbage)

    assert not readable(await tools.probe(picture))
    assert hostile == UNREADABLE or (isinstance(hostile, MediaFacts) and not readable(hostile))


async def test_a_call_past_its_time_or_its_memory_only_fails_itself(
    video: Path, tmp_path: Path
) -> None:
    slow = tmp_path / "slow-tool"
    slow.write_text("#!/bin/sh\nsleep 30\n")
    slow.chmod(slow.stat().st_mode | stat.S_IXUSR)
    timed = MediaTools(MediaLimits(seconds=1, memory_mb=512), tools=(str(slow), str(slow)))
    starved = MediaTools(MediaLimits(seconds=60, memory_mb=16))

    with pytest.raises(MediaError) as late:
        await timed.probe(video)
    with pytest.raises(MediaError) as cramped:
        await starved.probe(video)
    still = await MediaTools(LIMITS).probe(video)

    assert (late.value.code, cramped.value.code) == (UNREADABLE, UNREADABLE)
    assert readable(still)

"""A meeting's end, its ceiling, the silence rule and its minutes (notes plan step 1)."""

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.notes.domain.meetings import (
    MAX_LENGTH,
    SILENCE_AFTER,
    EndCause,
    MeetingClock,
    MeetingStatus,
    TitleRuleError,
    checked_title,
    end_meeting,
    ends_by,
    needs_run,
    sweep_cause,
    sweep_end,
    warn_at,
)
from shosai.features.notes.domain.minutes import (
    MAX_SECONDS,
    added_by_recording,
    meeting_seconds,
    recording_fits,
    seconds_between,
)

START = datetime(2026, 10, 19, 9, tzinfo=UTC)
offsets = st.timedeltas(min_value=timedelta(0), max_value=timedelta(hours=9))
causes = st.sampled_from([EndCause.CLIENT, EndCause.CLIENT_FAILED, EndCause.SILENCE])


@given(line=st.none() | offsets, now=offsets, asked=st.none() | offsets, cause=causes)
def test_ended_at_lies_between_the_last_line_and_now_or_six_hours(
    line: timedelta | None, now: timedelta, asked: timedelta | None, cause: EndCause
) -> None:
    last_line = None if line is None else START + min(line, now)
    clock = MeetingClock(START, last_line_end=last_line)
    ending = end_meeting(
        clock, cause=cause, now=START + now, asked=None if asked is None else START + asked
    )

    upper = min(START + now, ends_by(START))
    assert ending.changed
    assert START <= ending.ended_at <= upper
    if last_line is not None:
        assert ending.ended_at >= min(last_line, upper)


@given(first=offsets, again=offsets, cause=causes, repeat=causes)
def test_a_repeated_end_changes_nothing(
    first: timedelta, again: timedelta, cause: EndCause, repeat: EndCause
) -> None:
    ending = end_meeting(MeetingClock(START), cause=cause, now=START + first)
    ended = MeetingClock(START, ending.status, ending.ended_at)

    repeated = end_meeting(ended, cause=repeat, now=START + first + again, asked=START + again)

    assert not repeated.changed
    assert (repeated.status, repeated.ended_at) == (ending.status, ending.ended_at)


def test_a_client_reported_failure_ends_the_meeting_as_failed() -> None:
    ending = end_meeting(MeetingClock(START), cause=EndCause.CLIENT_FAILED, now=START + MAX_LENGTH)

    assert ending.status is MeetingStatus.FAILED


@given(audio=offsets, now=offsets)
def test_the_sweep_ends_five_minutes_after_the_last_audio_or_at_six_hours(
    audio: timedelta, now: timedelta
) -> None:
    last_audio = START + min(audio, now)
    clock = MeetingClock(START)

    cause = sweep_cause(clock, last_audio, START + now)
    ending = sweep_end(clock, last_audio, START + now)

    if now >= MAX_LENGTH:
        assert cause is EndCause.CEILING
    elif START + now - last_audio >= SILENCE_AFTER:
        assert cause is EndCause.SILENCE
    else:
        assert cause is None
    if ending is not None:
        assert ending.ended_at == min(last_audio, ends_by(START))


def test_a_long_pause_in_speech_does_not_close_a_recording_that_still_sends_audio() -> None:
    clock = MeetingClock(START, last_line_end=START + timedelta(minutes=5))
    now = START + timedelta(hours=1, minutes=5)

    assert sweep_cause(clock, now - timedelta(seconds=10), now) is None
    assert sweep_cause(clock, None, now) is EndCause.SILENCE


def test_the_warning_comes_ten_minutes_before_the_ceiling() -> None:
    assert ends_by(START) - warn_at(START) == timedelta(minutes=10)
    assert ends_by(START) - START == timedelta(hours=6)


def test_an_ended_meeting_is_not_swept() -> None:
    clock = MeetingClock(START, MeetingStatus.COMPLETED, START + timedelta(minutes=30))

    assert sweep_end(clock, None, START + timedelta(hours=7)) is None


def test_a_meeting_goes_to_processing_only_when_kept_and_spoken() -> None:
    assert needs_run(kept=True, has_speech=True)
    assert not needs_run(kept=False, has_speech=True)
    assert not needs_run(kept=True, has_speech=False)


def test_an_ended_clock_needs_its_end_and_an_active_one_none() -> None:
    with pytest.raises(ValueError, match="конца"):
        MeetingClock(START, MeetingStatus.COMPLETED)
    with pytest.raises(ValueError, match="конца"):
        MeetingClock(START, ended_at=START)


def test_a_title_is_trimmed_cut_and_never_empty() -> None:
    assert checked_title("  Встреча\x07 с клиентом ") == "Встреча с клиентом"
    assert len(checked_title("x" * 300)) == 256
    with pytest.raises(TitleRuleError):
        checked_title(" \n ")


@given(
    live=st.integers(min_value=0, max_value=10 * MAX_SECONDS),
    recording=st.none() | st.integers(min_value=0, max_value=10 * MAX_SECONDS),
)
def test_a_meeting_counts_once_and_never_beyond_six_hours(live: int, recording: int | None) -> None:
    total = meeting_seconds(live, recording)

    assert 0 <= total <= MAX_SECONDS
    assert total == min(max(live, recording or 0), MAX_SECONDS)
    if recording is not None:
        assert added_by_recording(live, recording) == total - min(live, MAX_SECONDS)
        assert added_by_recording(live, recording) >= 0


@given(span=st.timedeltas(min_value=timedelta(hours=-1), max_value=timedelta(hours=12)))
def test_seconds_between_stay_within_the_ceiling(span: timedelta) -> None:
    assert 0 <= seconds_between(START, START + span) <= MAX_SECONDS


def test_an_import_over_six_hours_does_not_fit() -> None:
    assert recording_fits(MAX_SECONDS)
    assert not recording_fits(MAX_SECONDS + 1)
    assert not recording_fits(0)

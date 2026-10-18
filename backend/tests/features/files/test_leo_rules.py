"""Leo's use as rules (files step 6): what counts against the knowledge limit, when a change
is refused, and the key of the person's Leo lock.
"""

import uuid

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.files.domain.kinds import LEO_EXTENSIONS, LEO_MAX_FILE_BYTES, leo_readable
from shosai.features.files.domain.leo import (
    KnowledgeLimitError,
    LeoCandidate,
    LeoShift,
    bytes_in_use,
)
from shosai.features.files.infrastructure.leo_lock import person_key

file_names = st.one_of(
    st.sampled_from(LEO_EXTENSIONS).map(lambda ext: f"File{ext}"),
    st.sampled_from([".png", ".mov", ".zip", ""]).map(lambda ext: f"File{ext}"),
)
candidates = st.builds(
    LeoCandidate,
    file_id=st.uuids(),
    name=file_names,
    size_bytes=st.integers(min_value=0, max_value=2 * LEO_MAX_FILE_BYTES),
    own=st.booleans(),
    folder=st.booleans(),
)
limits = st.one_of(st.none(), st.integers(min_value=0, max_value=4 * LEO_MAX_FILE_BYTES))


@given(st.lists(candidates, max_size=20))
def test_only_readable_files_leo_uses_count_against_the_limit(
    files: list[LeoCandidate],
) -> None:
    expected = sum(
        f.size_bytes for f in files if leo_readable(f.name, f.size_bytes) and (f.own or f.folder)
    )

    assert bytes_in_use(files) == expected


@given(candidates, candidates, st.integers(min_value=0, max_value=10**10), limits)
def test_a_change_that_starts_use_is_refused_exactly_when_it_passes_the_limit(
    before: LeoCandidate, after: LeoCandidate, others: int, limit: int | None
) -> None:
    after = LeoCandidate(before.file_id, after.name, before.size_bytes, after.own, after.folder)
    shift = LeoShift.of([(before, after)])
    in_use_after = others + (after.size_bytes if after.used else 0)
    passes = limit is not None and in_use_after > limit

    if shift.started and passes:
        with pytest.raises(KnowledgeLimitError):
            shift.check(in_use_after, limit)
    else:
        shift.check(in_use_after, limit)
    assert bool(shift.started) == (after.used and not before.used)
    assert bool(shift.stopped) == (before.used and not after.used)


def test_a_shift_that_only_stops_use_is_never_refused() -> None:
    used = LeoCandidate(uuid.uuid4(), "Notes.txt", 10, own=True, folder=False)
    idle = LeoCandidate(used.file_id, used.name, used.size_bytes, own=False, folder=False)

    LeoShift.of([(used, idle)]).check(in_use_after=10**12, limit=0)

    assert LeoShift.of([(used, used)]).empty


@given(st.uuids())
def test_the_lock_key_is_a_stable_signed_32_bit_integer(user_id: uuid.UUID) -> None:
    key = person_key(user_id)

    assert -(2**31) <= key < 2**31
    assert person_key(uuid.UUID(int=user_id.int)) == key


def test_ids_made_in_the_same_minute_get_different_lock_keys() -> None:
    ids = [uuid.uuid7() for _ in range(1000)]

    assert len({person_key(user_id) for user_id in ids}) > 990

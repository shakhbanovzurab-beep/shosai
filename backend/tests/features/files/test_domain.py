"""Files' rules: keys, the quota, uploads, Leo and names (files plan step 1; ADR 0055)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.files.domain.keys import PersonOwner, WorkspaceOwner, file_key, transient_key
from shosai.features.files.domain.kinds import (
    LEO_EXTENSIONS,
    LEO_MAX_FILE_BYTES,
    FileKind,
    kind_of,
    leo_readable,
    opens_inline,
)
from shosai.features.files.domain.leo import LeoVia, fits_knowledge, leo_use
from shosai.features.files.domain.names import NameRule, NameRuleError, checked_name
from shosai.features.files.domain.purposes import PURPOSES, UploadPurpose, within_cap
from shosai.features.files.domain.quota import (
    OverLimitMark,
    QuotaAction,
    QuotaExceededError,
    StoredFile,
    Usage,
    newest_over_limit,
    quota_action,
    reminder_due,
    removal_due,
    reserve,
)
from shosai.features.files.domain.uploads import MAX_PARTS, MIN_PART_BYTES, part_sizes

START = datetime(2026, 10, 18, tzinfo=UTC)
names = st.text(min_size=1, max_size=120)
owners = st.one_of(st.builds(PersonOwner, st.uuids()), st.builds(WorkspaceOwner, st.uuids()))


@given(owner=owners, file_id=st.uuids(), name=names)
def test_a_key_carries_the_full_owner_id_and_never_the_home_or_the_name(
    owner: PersonOwner | WorkspaceOwner, file_id: uuid.UUID, name: str
) -> None:
    key = file_key(owner, file_id)
    owner_id = owner.user_id if isinstance(owner, PersonOwner) else owner.org_id

    assert key.startswith(("u/", "o/"))
    assert str(owner_id) in key
    assert not any(home in key.split("/") for home in ("ru", "eu", "RU", "EU"))
    assert len(name) < 4 or name not in key.replace(str(owner_id), "").replace(str(file_id), "")


@given(purpose=st.sampled_from(list(UploadPurpose)), upload_id=st.uuids())
def test_a_transient_key_names_its_purpose_and_upload_only(
    purpose: UploadPurpose, upload_id: uuid.UUID
) -> None:
    assert transient_key(purpose, upload_id) == f"transient/{purpose.value}/{upload_id}"


@given(
    used=st.integers(0, 10**12),
    reserved=st.integers(0, 10**12),
    limit=st.none() | st.integers(0, 10**12),
    size=st.integers(1, 10**12),
)
def test_a_reservation_never_lets_usage_pass_the_limit(
    used: int, reserved: int, limit: int | None, size: int
) -> None:
    usage = Usage(used, reserved)
    try:
        after = reserve(usage, limit, size)
    except QuotaExceededError:
        assert limit is not None
        assert usage.total + size > limit
    else:
        assert limit is None or after.total <= limit
        assert after.total == usage.total + size


@given(name=st.text(max_size=40), size=st.integers(0, 2 * LEO_MAX_FILE_BYTES))
def test_leo_reads_what_the_cabinet_says_it_reads(name: str, size: int) -> None:
    expected = size <= LEO_MAX_FILE_BYTES and name.lower().endswith(LEO_EXTENSIONS)

    assert leo_readable(name, size) is expected


def test_kinds_follow_the_cabinet_s_extensions_and_active_content_never_opens_inline() -> None:
    assert [kind_of(n) for n in ("Report.PDF", "plan.docx", "x.fig", "notes", ".env")] == [
        FileKind.PDF, FileKind.DOCUMENT, FileKind.DESIGN, FileKind.OTHER, FileKind.OTHER,
    ]  # fmt: skip
    assert opens_inline("application/pdf")
    assert not opens_inline("text/html; charset=utf-8")
    assert not opens_inline("image/svg+xml")


@pytest.mark.parametrize(
    ("raw", "rule"),
    [("   ", NameRule.REQUIRED), ("a" * 121, NameRule.TOO_LONG), ("a/b", NameRule.SLASH),
     ("a\\b", NameRule.SLASH), ("a\nb", NameRule.CONTROL)],
)  # fmt: skip
def test_a_name_names_the_rule_it_breaks(raw: str, rule: NameRule) -> None:
    with pytest.raises(NameRuleError) as refused:
        checked_name(raw)

    assert refused.value.code == rule.value


def test_a_name_is_trimmed_and_duplicates_are_allowed() -> None:
    assert checked_name("  Report.pdf ") == "Report.pdf"


@given(size=st.integers(1, PURPOSES[UploadPurpose.FILE_MANAGER].max_bytes))
def test_parts_cover_the_upload_exactly_within_the_store_s_limits(size: int) -> None:
    parts = part_sizes(size)

    assert sum(parts) == size
    assert len(parts) <= MAX_PARTS
    assert all(part >= MIN_PART_BYTES for part in parts[:-1])


def test_each_purpose_has_its_cap() -> None:
    assert within_cap(UploadPurpose.FILE_MANAGER, 2 * 1024**3)
    assert not within_cap(UploadPurpose.FILE_MANAGER, 2 * 1024**3 + 1)
    assert not within_cap(UploadPurpose.LEO_ATTACHMENT, 10 * 1024**2 + 1)
    assert not within_cap(UploadPurpose.RECORDING, 0)


def test_over_the_limit_reminders_go_once_in_order_and_removal_waits_90_days() -> None:
    def at(days: float) -> datetime:
        return START + timedelta(days=days)

    assert reminder_due(START, at(59), sent=0) is None
    assert reminder_due(START, at(60), sent=0) == 0
    assert reminder_due(START, at(60), sent=1) is None
    assert reminder_due(START, at(83), sent=1) == 1
    assert reminder_due(START, at(89), sent=2) == 2
    assert reminder_due(START, at(95), sent=3) is None
    assert not removal_due(START, at(89.9))
    assert removal_due(START, at(90))


@given(
    sizes=st.lists(st.integers(1, 10**9), min_size=1, max_size=30),
    limit=st.integers(0, 10**10),
)
def test_removal_takes_the_newest_files_until_what_stays_fits(sizes: list[int], limit: int) -> None:
    files = [
        StoredFile(uuid.uuid4(), size, START + timedelta(minutes=i)) for i, size in enumerate(sizes)
    ]
    used = sum(sizes)

    chosen = newest_over_limit(files, used, limit)

    kept = [f for f in files if f.file_id not in chosen]
    assert sum(f.size_bytes for f in kept) <= limit or not kept
    newest_first = [f.file_id for f in sorted(files, key=lambda f: f.created_at, reverse=True)]
    assert chosen == newest_first[: len(chosen)]
    if chosen:
        assert (
            sum(f.size_bytes for f in kept)
            + files[[f.file_id for f in files].index(chosen[-1])].size_bytes
            > limit
        )


def test_leo_uses_a_readable_file_by_its_own_switch_or_its_folder_s() -> None:
    assert leo_use(readable=True, own=True, folder=True) is LeoVia.FILE
    assert leo_use(readable=True, own=False, folder=True) is LeoVia.FOLDER
    assert leo_use(readable=False, own=True, folder=True) is None
    assert fits_knowledge(90, 10, 100)
    assert not fits_knowledge(90, 11, 100)
    assert fits_knowledge(10**12, 1, None)


def test_the_quota_takes_one_step_at_a_time() -> None:
    since = datetime(2026, 1, 1, tzinfo=UTC)
    over, under = Usage(used=11, reserved=0), Usage(used=9, reserved=5)

    assert quota_action(under, 10, OverLimitMark(None, 0), since) is None
    assert quota_action(under, 10, OverLimitMark(since, 2), since) is QuotaAction.CLEAR
    assert quota_action(over, None, OverLimitMark(since, 1), since) is QuotaAction.CLEAR
    assert quota_action(over, 10, OverLimitMark(None, 0), since) is QuotaAction.MARK
    assert quota_action(over, 10, OverLimitMark(since, 0), since + timedelta(days=59)) is None
    assert quota_action(over, 10, OverLimitMark(since, 0), since + timedelta(days=60)) is (
        QuotaAction.REMIND
    )
    assert quota_action(over, 10, OverLimitMark(since, 1), since + timedelta(days=61)) is None
    assert quota_action(over, 10, OverLimitMark(since, 3), since + timedelta(days=90)) is (
        QuotaAction.REMOVE
    )

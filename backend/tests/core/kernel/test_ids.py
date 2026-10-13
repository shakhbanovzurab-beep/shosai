"""Platform ids are UUIDv7: unique and ordered by creation time."""

from shosai.core.kernel.ids import new_id


def test_ids_are_version_7_and_sort_by_creation() -> None:
    ids = [new_id() for _ in range(1000)]

    assert {item.version for item in ids} == {7}
    assert len(set(ids)) == len(ids)
    assert ids == sorted(ids)

"""Shareable resource declarations name real columns and stay unique across slices (§7)."""

import pytest
from sqlalchemy import Column, MetaData, Table, Text, Uuid

from shosai.composition.features import check_features, shareable_resources
from shosai.core.access.shareable import ShareableResource, ShareableResourceError
from shosai.core.features import FeatureModule

METADATA = MetaData()
NOTES = Table(
    "fixture_notes",
    METADATA,
    Column("id", Uuid, primary_key=True),
    Column("user_id", Uuid),
    Column("org_id", Uuid),
    Column("access", Text),
)
FOLDERS = Table(
    "fixture_folders",
    METADATA,
    Column("folder_id", Uuid, primary_key=True),
    Column("owner_id", Uuid),
    Column("org_id", Uuid),
    Column("access", Text),
)


def test_a_declaration_with_default_columns_is_accepted() -> None:
    notes = ShareableResource("note", NOTES)

    assert notes.column_names() == ("id", "user_id", "org_id", "access")


def test_a_declaration_may_name_its_own_columns() -> None:
    folders = ShareableResource("folder", FOLDERS, id="folder_id", owner="owner_id")

    assert folders.column_names() == ("folder_id", "owner_id", "org_id", "access")


def test_a_missing_column_is_refused_by_name() -> None:
    with pytest.raises(ShareableResourceError, match="owner_id"):
        ShareableResource("note", NOTES, owner="owner_id")


@pytest.mark.parametrize("kind", ["", "Note", "note-item", "1note", "n" * 33])
def test_a_kind_is_short_snake_case(kind: str) -> None:
    with pytest.raises(ShareableResourceError, match="snake_case"):
        ShareableResource(kind, NOTES)


def test_composition_lists_every_slice_resource() -> None:
    notes = ShareableResource("note", NOTES)
    folders = ShareableResource("folder", FOLDERS, id="folder_id", owner="owner_id")
    features = [
        FeatureModule(name="alpha", shareable=(notes,)),
        FeatureModule(name="beta", shareable=(folders,)),
    ]

    check_features(features)

    assert shareable_resources(features) == [notes, folders]


@pytest.mark.parametrize(
    ("second", "label"),
    [
        (ShareableResource("note", FOLDERS, id="folder_id", owner="owner_id"), "вид"),
        (ShareableResource("memo", NOTES), "таблица"),
    ],
)
def test_one_kind_and_one_table_have_one_owner(second: ShareableResource, label: str) -> None:
    features = [
        FeatureModule(name="alpha", shareable=(ShareableResource("note", NOTES),)),
        FeatureModule(name="beta", shareable=(second,)),
    ]

    with pytest.raises(ValueError, match=label):
        check_features(features)


TASKS = Table(
    "fixture_tasks",
    METADATA,
    Column("id", Uuid, primary_key=True),
    Column("user_id", Uuid),
    Column("org_id", Uuid),
    Column("access", Text),
    Column("note_id", Uuid),
    Column("assignee_id", Uuid),
)


def test_a_declaration_may_name_a_parent_and_a_reader() -> None:
    tasks = ShareableResource("task", TASKS, parent=("note", "note_id"), reader="assignee_id")

    assert tasks.rule_columns() == ("note_id", "assignee_id")
    assert ShareableResource("note", NOTES).rule_columns() == ()


@pytest.mark.parametrize(
    ("parent", "reader", "match"),
    [
        (("note", "missing_id"), None, "missing_id"),
        (None, "missing_id", "missing_id"),
        (("task", "note_id"), None, "родитель"),
        (("Note", "note_id"), None, "родитель"),
    ],
)
def test_the_rule_columns_and_the_parent_kind_are_checked(
    parent: tuple[str, str] | None, reader: str | None, match: str
) -> None:
    with pytest.raises(ShareableResourceError, match=match):
        ShareableResource("task", TASKS, parent=parent, reader=reader)


def test_a_parent_no_slice_declares_or_a_chain_of_parents_is_refused() -> None:
    notes = ShareableResource("note", NOTES)
    tasks = ShareableResource("task", TASKS, parent=("note", "note_id"))
    folders = ShareableResource("folder", FOLDERS, id="folder_id", owner="owner_id")
    chained = ShareableResource(
        "folder", FOLDERS, id="folder_id", owner="owner_id", parent=("task", "org_id")
    )

    check_features([FeatureModule(name="alpha", shareable=(notes, tasks, folders))])
    with pytest.raises(ValueError, match="родитель note"):
        check_features([FeatureModule(name="alpha", shareable=(tasks, folders))])
    with pytest.raises(ValueError, match="родитель task"):
        check_features([FeatureModule(name="alpha", shareable=(notes, tasks, chained))])

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

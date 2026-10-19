"""Folders, the person's own notes and participants (meetings plan step 1)."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.meetings.domain.library import (
    NATIVE_NOTES_MAX_BYTES,
    PARTICIPANTS_MAX,
    FolderColor,
    LibraryRule,
    LibraryRuleError,
    NoteClient,
    ParticipantSource,
    checked_folder_name,
    checked_notes,
    folder_color,
    may_add_participant,
    next_version,
    normalized_email,
    note_client,
    participant_name,
    removable,
)


def test_folders_take_the_cabinets_colours_in_turn() -> None:
    colours = [folder_color(count) for count in range(6)]

    assert colours[:5] == [
        FolderColor.GREEN,
        FolderColor.VIOLET,
        FolderColor.RED,
        FolderColor.BLUE,
        FolderColor.AMBER,
    ]
    assert colours[5] is FolderColor.GREEN


@pytest.mark.parametrize(
    ("raw", "rule"),
    [(" \t", LibraryRule.FOLDER_NAME_REQUIRED), ("п" * 41, LibraryRule.FOLDER_NAME_TOO_LONG)],
)
def test_a_folder_name_is_one_to_forty_characters(raw: str, rule: LibraryRule) -> None:
    with pytest.raises(LibraryRuleError) as raised:
        checked_folder_name(raw)

    assert raised.value.code == rule.value
    assert checked_folder_name("  Клиенты   2026 ") == "Клиенты 2026"


@given(version=st.integers(0, 10**6))
def test_every_write_raises_the_version_by_one(version: int) -> None:
    assert next_version(version) == version + 1


def test_an_unknown_client_writes_as_web() -> None:
    assert note_client("macOS") is NoteClient.MACOS
    assert note_client("ios") is NoteClient.WEB
    assert note_client(None) is NoteClient.WEB


def test_notes_keep_their_routes_caps() -> None:
    assert checked_notes("я" * 50_000, native=False)
    with pytest.raises(LibraryRuleError):
        checked_notes("я" * 50_001, native=False)
    with pytest.raises(LibraryRuleError):
        checked_notes("я" * (NATIVE_NOTES_MAX_BYTES // 2 + 1), native=True)


def test_participants_are_addresses_and_only_added_ones_go() -> None:
    assert normalized_email("  Anna@Example.COM ") == "anna@example.com"
    for raw in ("anna", "anna@", "a b@c.d", "@c.d"):
        with pytest.raises(LibraryRuleError):
            normalized_email(raw)
    assert participant_name("  Анна  Петрова ") == "Анна Петрова"
    assert participant_name(" ") is None
    assert removable(ParticipantSource.ADDED)
    assert not removable(ParticipantSource.CALENDAR)
    assert not removable(ParticipantSource.SPEAKER)
    assert may_add_participant(PARTICIPANTS_MAX - 1)
    assert not may_add_participant(PARTICIPANTS_MAX)

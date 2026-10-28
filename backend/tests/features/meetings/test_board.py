"""The board's rules (meetings A11b, MR-D13): its limits and its picture's name."""

from datetime import UTC, datetime

import pytest

from shosai.features.meetings.domain.board import (
    ELEMENTS_BYTES,
    ELEMENTS_MAX,
    FILES_BYTES,
    SceneSize,
    fits,
    picture_name,
)


@pytest.mark.parametrize(
    "size", [SceneSize(0, 2, 2), SceneSize(ELEMENTS_MAX, ELEMENTS_BYTES, FILES_BYTES)]
)
def test_a_scene_within_its_limits_fits(size: SceneSize) -> None:
    assert fits(size)


@pytest.mark.parametrize(
    "size",
    [
        SceneSize(ELEMENTS_MAX + 1, 2, 2),
        SceneSize(1, ELEMENTS_BYTES + 1, 2),
        SceneSize(1, 2, FILES_BYTES + 1),
    ],
)
def test_a_scene_over_its_elements_their_bytes_or_its_images_does_not(size: SceneSize) -> None:
    assert not fits(size)


def test_the_picture_is_named_after_the_meeting_and_its_start() -> None:
    started = datetime(2026, 10, 28, 9, 5, tzinfo=UTC)

    assert picture_name("Design review", started) == "Design review 2026-10-28 09-05 board.png"
    assert picture_name(None, started) == "Meeting 2026-10-28 09-05 board.png"

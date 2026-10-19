"""What a shared page shows of people (MT-D5; the cabinet's `notes/mocks/shared-note.ts`).

A shared page never shows an email. With names shown, it lists the participants by name
and names speakers and owners; with names hidden, it gives only how many people took part,
no owner, and numbers the speakers 1, 2, 3 … in the order they first speak — the reader's
interface words the number ("Speaker 2"). A name holding an "@" is never shown: it may be
an address or a part of one.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Person:
    """A participant as stored: a name if known and an address if known."""

    name: str | None
    email: str | None = None


@dataclass(frozen=True, slots=True)
class PeopleView:
    """The participants a page shows: their names, or None with names hidden, and a count."""

    names: tuple[str, ...] | None
    count: int


@dataclass(frozen=True, slots=True)
class SpeakerView:
    """A speaker on a page: the number by first appearance, and the name when names show."""

    number: int
    name: str | None


def shown_name(name: str | None) -> str | None:
    """A name fit for a page: trimmed, not empty and without an "@"."""
    if name is None:
        return None
    clean = " ".join(name.split())
    return clean if clean and "@" not in clean else None


def people_view(participants: Sequence[Person], *, show_names: bool) -> PeopleView:
    """The page's participants: names without addresses, or only their count."""
    if not show_names:
        return PeopleView(None, len(participants))
    names = tuple(name for name in (shown_name(p.name) for p in participants) if name)
    return PeopleView(names, len(participants))


def first_appearance(speakers: Iterable[int | None]) -> dict[int, int]:
    """Each speaker's number, 1 and up, in the order they first speak."""
    numbers: dict[int, int] = {}
    for speaker in speakers:
        if speaker is not None and speaker not in numbers:
            numbers[speaker] = len(numbers) + 1
    return numbers


def speaker_views(
    speakers: Sequence[int | None], names: Mapping[int, str | None], *, show_names: bool
) -> dict[int, SpeakerView]:
    """How each speaker of the transcript `speakers` appears on the page."""
    return {
        speaker: SpeakerView(number, shown_name(names.get(speaker)) if show_names else None)
        for speaker, number in first_appearance(speakers).items()
    }


def owner_view(owner_name: str | None, *, show_names: bool) -> str | None:
    """An action item's owner on the page: the name when names show, else nobody."""
    return shown_name(owner_name) if show_names else None

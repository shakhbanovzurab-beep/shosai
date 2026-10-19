"""The share link and what a shared page shows of people (meetings plan step 1; MT-D5)."""

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.meetings.domain.redaction import (
    Person,
    first_appearance,
    owner_view,
    people_view,
    speaker_views,
)
from shosai.features.meetings.domain.sharing import (
    COMMENT_AUTHOR_MAX,
    CommentRuleError,
    LinkState,
    ShareExpiry,
    ShareSettings,
    checked_comment,
    expires_at,
    new_token,
    next_expires_at,
    resolves,
    well_formed,
)

NOW = datetime(2026, 10, 19, 9, tzinfo=UTC)
emails = st.emails()
names = st.none() | st.text(max_size=40) | emails


@given(
    people=st.lists(st.builds(Person, names, st.none() | emails), max_size=12), shown=st.booleans()
)
def test_a_shared_page_never_shows_an_address(people: list[Person], *, shown: bool) -> None:
    view = people_view(people, show_names=shown)
    addresses = [p.email for p in people if p.email] + [
        p.name for p in people if p.name and "@" in p.name
    ]

    assert view.count == len(people)
    assert (view.names is None) is not shown
    assert not any(address in name for name in view.names or () for address in addresses if address)
    assert all("@" not in name for name in view.names or ())


@given(speakers=st.lists(st.none() | st.integers(0, 6), max_size=40), shown=st.booleans())
def test_speakers_are_numbered_by_first_appearance(
    speakers: list[int | None], *, shown: bool
) -> None:
    order = list(dict.fromkeys(s for s in speakers if s is not None))
    names = {
        speaker: f"person{speaker}@example.com" if speaker % 2 else "Анна" for speaker in order
    }

    views = speaker_views(speakers, names, show_names=shown)

    assert [views[speaker].number for speaker in order] == list(range(1, len(order) + 1))
    assert all(v.name is None or "@" not in v.name for v in views.values())
    if not shown:
        assert all(v.name is None for v in views.values())
    assert first_appearance(speakers) == {s: i + 1 for i, s in enumerate(order)}


def test_an_owner_shows_only_with_names() -> None:
    assert owner_view(" Анна ", show_names=True) == "Анна"
    assert owner_view("Анна", show_names=False) is None
    assert owner_view("anna@example.com", show_names=True) is None


def test_a_token_is_43_url_safe_characters_and_draft_tokens_pass() -> None:
    token = new_token()

    assert len(token) == 43
    assert well_formed(token)
    assert well_formed("abc_DEF-123")
    assert not well_formed("../etc")
    assert not well_formed("a" * 65)


def test_expiry_counts_from_when_it_was_chosen() -> None:
    week = ShareSettings(expiry=ShareExpiry.DAYS_7)
    later = NOW + timedelta(days=3)

    assert expires_at(ShareExpiry.NEVER, NOW) is None
    assert expires_at(ShareExpiry.DAYS_90, NOW) == NOW + timedelta(days=90)
    assert next_expires_at(None, week, None, NOW) == NOW + timedelta(days=7)
    kept = next_expires_at(
        week, ShareSettings(show_names=True, expiry=ShareExpiry.DAYS_7), NOW, later
    )
    assert kept == NOW
    assert next_expires_at(week, ShareSettings(), NOW, later) is None


@given(
    expiry=st.none() | st.timedeltas(min_value=timedelta(days=-3), max_value=timedelta(days=3)),
    hidden=st.booleans(),
    kept=st.booleans(),
    owner_hidden=st.booleans(),
)
def test_a_link_opens_only_when_on_time_kept_and_nobody_hidden(
    expiry: timedelta | None, *, hidden: bool, kept: bool, owner_hidden: bool
) -> None:
    ends = None if expiry is None else NOW + expiry
    state = LinkState(ends, meeting_hidden=hidden, meeting_kept=kept, owner_hidden=owner_hidden)

    expected = kept and not hidden and not owner_hidden and (ends is None or ends > NOW)
    assert resolves(state, NOW) is expected


def test_a_comment_needs_text_and_a_short_author() -> None:
    assert checked_comment("  ", " Отлично ") == (None, "Отлично")
    assert checked_comment(" Гость  Петя ", "ок") == ("Гость Петя", "ок")
    for author, text in ((None, " "), (None, "x" * 2001), ("a" * (COMMENT_AUTHOR_MAX + 1), "ок")):
        with pytest.raises(CommentRuleError):
            checked_comment(author, text)

"""Seats, slugs, invitation tokens and company domains (workspaces plan §3.4, ADR 0053)."""

import itertools
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.workspaces.domain.domains import (
    CompanyDomain,
    DomainRefusal,
    DomainRefusedError,
)
from shosai.features.workspaces.domain.invitations import (
    INVITATION_LIFETIME,
    InvalidInvitationTokenError,
    InvitationToken,
    is_expired,
)
from shosai.features.workspaces.domain.seats import (
    SeatUse,
    seats_at_creation_valid,
    seats_change_valid,
)
from shosai.features.workspaces.domain.slugs import SLUG_MAX_LENGTH, base_slug, slug_candidates

counts = st.integers(0, 600)


@given(counts, counts, counts, st.integers(0, 30))
def test_pending_invitations_hold_seats(
    paid: int, members: int, pending: int, newcomers: int
) -> None:
    use = SeatUse(paid, members, pending)

    assert use.admits(newcomers) is (members + pending + newcomers <= paid)
    assert use.left >= 0
    assert use.admits(0) is (members + pending <= paid)


@pytest.mark.parametrize(("seats", "valid"), [(1, False), (2, True), (100, True), (101, False)])
def test_a_new_workspace_starts_with_2_to_100_seats(seats: int, *, valid: bool) -> None:
    assert seats_at_creation_valid(seats) is valid


@given(counts, counts, st.integers(0, 700))
def test_the_platform_never_sets_fewer_seats_than_taken_or_more_than_500(
    members: int, pending: int, seats: int
) -> None:
    use = SeatUse(10, members, pending)

    assert seats_change_valid(seats, use) is (members + pending <= seats <= 500)


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("Lumen Labs", "lumen-labs"),
        ("  Acme, Inc.  ", "acme-inc"),
        ("Моя Компания", "моя-компания"),
        ("株式会社 ルーメン", "株式会社-ルーメン"),
        ("New", "workspace"),
        ("!!!", "workspace"),
        ("ＦＵＬＬ　ＷＩＤＴＨ", "full-width"),
    ],
)
def test_a_slug_keeps_letters_of_every_script(name: str, slug: str) -> None:
    assert base_slug(name) == slug


@given(st.text(max_size=120))
def test_every_name_gives_a_short_slug_without_edge_hyphens_and_never_new(name: str) -> None:
    for candidate in itertools.islice(slug_candidates(name), 12):
        assert 0 < len(candidate) <= SLUG_MAX_LENGTH
        assert not candidate.startswith("-")
        assert not candidate.endswith("-")
        assert candidate != "new"


@given(st.text(max_size=120))
def test_collision_candidates_are_all_different(name: str) -> None:
    candidates = list(itertools.islice(slug_candidates(name), 30))

    assert len(set(candidates)) == len(candidates)


@given(st.binary(min_size=32, max_size=32))
def test_a_token_survives_its_link_and_only_its_digest_matches(raw: bytes) -> None:
    token = InvitationToken.from_random(raw)

    parsed = InvitationToken.parse(token.value)

    other = InvitationToken.from_random(bytes(byte ^ 0xFF for byte in raw))

    assert parsed == token
    assert parsed.matches(token.digest())
    assert not parsed.matches(other.digest())


@pytest.mark.parametrize("text", ["", "short", "A" * 43 + "=", "!" * 43, "A" * 44])
def test_anything_but_a_token_is_refused_before_any_lookup(text: str) -> None:
    with pytest.raises(InvalidInvitationTokenError):
        InvitationToken.parse(text)


def test_a_token_needs_exactly_32_random_bytes() -> None:
    with pytest.raises(InvalidInvitationTokenError):
        InvitationToken.from_random(bytes(16))


def test_a_link_works_for_14_days() -> None:
    sent = datetime(2026, 10, 1, tzinfo=UTC)

    assert timedelta(days=14) == INVITATION_LIFETIME
    assert not is_expired(sent, sent + timedelta(days=14) - timedelta(seconds=1))
    assert is_expired(sent, sent + timedelta(days=14))


@pytest.mark.parametrize(
    ("raw", "domain"),
    [
        ("Acme.COM.", "acme.com"),
        ("  mail.acme.co.uk ", "mail.acme.co.uk"),
        ("Пример.РФ", "xn--e1afmkfd.xn--p1ai"),
    ],
)
def test_a_company_domain_is_normalized_like_an_address_domain(raw: str, domain: str) -> None:
    assert CompanyDomain.parse(raw).value == domain


@pytest.mark.parametrize(
    ("raw", "refusal"),
    [
        ("gmail.com", DomainRefusal.PUBLIC),
        ("Yandex.RU", DomainRefusal.PUBLIC),
        ("localhost", DomainRefusal.INVALID),
        ("-acme.com", DomainRefusal.INVALID),
        ("acme..com", DomainRefusal.INVALID),
        ("acme_corp.com", DomainRefusal.INVALID),
        ("10.0.0.1", DomainRefusal.INVALID),
        ("a" * 64 + ".com", DomainRefusal.INVALID),
        ("", DomainRefusal.INVALID),
    ],
)
def test_public_and_malformed_domains_are_refused(raw: str, refusal: DomainRefusal) -> None:
    with pytest.raises(DomainRefusedError) as problem:
        CompanyDomain.parse(raw)

    assert problem.value.refusal is refusal


def test_the_txt_record_names_shosai_and_the_token() -> None:
    record = CompanyDomain.parse("acme.com").verification_record("t0k3n")

    assert record == "shosai-domain-verification=t0k3n"

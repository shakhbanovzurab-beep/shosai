"""States of grants and connections, and the scopes a flow asks for (plan §3.4, §3.8)."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.connectors.domain.catalogue import CATALOGUE, App, Owner, spec_of
from shosai.features.connectors.domain.scopes import (
    covers,
    merged_scopes,
    missing_scopes,
    parse_scope,
    requested_scopes,
)
from shosai.features.connectors.domain.states import (
    ACTIVE_CONNECTION,
    ACTIVE_GRANT,
    CONNECTION_PROBLEMS,
    GRANT_PROBLEMS,
    ConnectionState,
    ConnectionStatus,
    GrantState,
    GrantStatus,
    Problem,
    StateRuleError,
    broken_transition,
    connection_broken,
    grant_broken,
    shown_state,
)

grant_states = st.one_of(
    st.just(ACTIVE_GRANT),
    st.just(GrantState(GrantStatus.REVOKING)),
    st.sampled_from(sorted(GRANT_PROBLEMS)).map(grant_broken),
)
own_states = st.one_of(
    st.just(ACTIVE_CONNECTION), st.sampled_from(sorted(CONNECTION_PROBLEMS)).map(connection_broken)
)
scope_sets = st.frozensets(st.sampled_from(["a", "b", "c", "d", "e"]), max_size=5)


def test_every_problem_belongs_to_the_grant_or_to_one_app() -> None:
    assert set(Problem) == GRANT_PROBLEMS | CONNECTION_PROBLEMS
    assert not GRANT_PROBLEMS & CONNECTION_PROBLEMS


@given(grant=grant_states, own=own_states)
def test_a_connection_needs_its_person_exactly_when_it_shows_a_problem(
    grant: GrantState, own: ConnectionState
) -> None:
    shown = shown_state(grant, own)

    assert (shown.status is ConnectionStatus.NEEDS_RECONNECT) == (shown.problem is not None)
    if not grant.usable:
        assert shown.status is ConnectionStatus.NEEDS_RECONNECT
    if grant.problem is not None:
        assert shown.problem is grant.problem
    if grant.usable:
        assert shown == own


@given(before=own_states, after=own_states)
def test_broken_is_news_only_on_the_way_from_working_to_waiting(
    before: ConnectionState, after: ConnectionState
) -> None:
    assert broken_transition(before, after) == (
        before.status is ConnectionStatus.ACTIVE
        and after.status is ConnectionStatus.NEEDS_RECONNECT
    )


def test_inconsistent_states_are_refused() -> None:
    with pytest.raises(StateRuleError):
        GrantState(GrantStatus.NEEDS_RECONNECT)
    with pytest.raises(StateRuleError):
        GrantState(GrantStatus.ACTIVE, Problem.REFRESH_REFUSED)
    with pytest.raises(StateRuleError):
        grant_broken(Problem.SCOPE_MISSING)
    with pytest.raises(StateRuleError):
        connection_broken(Problem.REFRESH_REFUSED)
    with pytest.raises(StateRuleError):
        ConnectionState(ConnectionStatus.ACTIVE, Problem.SCOPE_MISSING)


@given(held=scope_sets, app=st.sampled_from(sorted(CATALOGUE)), union=st.booleans())
def test_a_flow_asks_for_the_app_and_keeps_the_account_s_rights_where_required(
    held: frozenset[str], app: App, *, union: bool
) -> None:
    spec = spec_of(app)
    asked = requested_scopes(spec, Owner.PERSON, held=held, union_required=union)

    assert spec.scopes <= asked
    assert (held <= asked) or not union
    if not union:
        assert asked == spec.scopes


@given(app=st.sampled_from(sorted(CATALOGUE)), granted=scope_sets, extra=scope_sets)
def test_a_grant_covers_an_app_exactly_when_nothing_is_missing(
    app: App, granted: frozenset[str], extra: frozenset[str]
) -> None:
    spec = spec_of(app)

    assert covers(spec, Owner.PERSON, granted) == (not missing_scopes(spec, Owner.PERSON, granted))
    assert covers(spec, Owner.PERSON, spec.scopes | extra)
    merged = merged_scopes(granted, extra)
    assert granted <= merged
    assert extra <= merged


def test_a_missing_box_on_google_s_screen_is_named() -> None:
    calendar = spec_of(App.GOOGLE_CALENDAR)
    granted = calendar.scopes - {"https://www.googleapis.com/auth/calendar.events"}

    assert missing_scopes(calendar, Owner.PERSON, granted) == {
        "https://www.googleapis.com/auth/calendar.events"
    }


def test_a_scope_field_is_read_with_its_provider_s_separator() -> None:
    assert parse_scope("openid  email ") == {"openid", "email"}
    assert parse_scope("read_api,read_user", ",") == {"read_api", "read_user"}
    assert parse_scope(None) == frozenset()

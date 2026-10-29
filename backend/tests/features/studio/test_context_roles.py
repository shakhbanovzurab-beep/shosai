"""Where a person's own words go (ST-D2 as amended by the owner on 2026-10-29): every role, which
also takes a role added later, or the roles named; Leo always takes them."""

import pytest

from shosai.features.studio.domain.context_roles import ContextRoles
from shosai.features.studio.domain.roles import PromptRole


def test_every_role_takes_the_words_and_leo_always_does() -> None:
    every, none = ContextRoles.of("all"), ContextRoles.of([])

    assert all(every.reaches(role) for role in PromptRole)
    assert not any(none.reaches(role) for role in PromptRole)
    assert (every.reaches(None), none.reaches(None)) == (True, True)


def test_the_roles_named_go_in_the_roles_order_without_repeats() -> None:
    chosen = ContextRoles.of([PromptRole.NOTES, PromptRole.CODE, PromptRole.NOTES])

    assert chosen.wire() == [PromptRole.CODE, PromptRole.NOTES]
    assert ContextRoles().wire() == "all"
    assert not chosen.reaches(PromptRole.LIVE_ANSWERS)


def test_every_role_names_no_role() -> None:
    with pytest.raises(ValueError, match="все роли"):
        ContextRoles(every=True, named=frozenset({PromptRole.CODE}))

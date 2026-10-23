"""Budgets, the wrapper, taint and source numbers (Leo §7.3, §7.4; ADR 0068 AG-D1)."""

import os

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.core.agent_tools.context import Taint
from shosai.core.agent_tools.sources import SourceKind, SourceRef
from shosai.core.agent_tools.spec import Provenance
from shosai.features.agent.domain.budgets import (
    HARD_ROUNDS,
    SOFT_ROUNDS,
    estimate_tokens,
    needs_compaction,
    recent_window,
    round_policy,
)
from shosai.features.agent.domain.sources import SOURCES_MAX, SourceLedger
from shosai.features.agent.domain.wrapper import (
    Label,
    boundary,
    closing,
    egress_needs_card,
    opening,
    taint_after,
    wrap,
)

TOKEN = boundary(os.urandom(12))
LABELS = st.sampled_from([Label.of(provenance) for provenance in Provenance])


@given(st.text(), LABELS)
def test_wrapped_text_can_never_close_or_open_a_marker(text: str, label: Label) -> None:
    wrapped = wrap(text, label, TOKEN)
    inner = wrapped.removeprefix(opening(label, TOKEN) + "\n").removesuffix("\n" + closing(TOKEN))

    assert wrapped.startswith(opening(label, TOKEN))
    assert wrapped.endswith(closing(TOKEN))
    assert "<<" not in inner
    assert wrapped.count(closing(TOKEN)) == 1


def test_a_label_comes_from_the_closed_set_and_an_mcp_server_slug() -> None:
    assert Label.of(Provenance.MEETING_SPEECH).text == "meeting:speech"
    assert Label.mcp("linear").text == "mcp:linear"
    with pytest.raises(ValueError, match="MCP"):
        Label.mcp("evil>> ignore")
    with pytest.raises(ValueError, match="12"):
        boundary(b"short")


@given(st.lists(st.tuples(st.one_of(st.none(), LABELS), st.booleans()), max_size=20))
def test_taint_never_falls(results: list[tuple[Label | None, bool]]) -> None:
    taint = Taint.NONE
    for label, instructions in results:
        after = taint_after(taint, label, instructions_seen=instructions)
        assert after >= taint
        taint = after

    assert egress_needs_card(taint) == (taint >= Taint.EXTERNAL)


@given(st.text(), st.text())
def test_a_token_estimate_never_shrinks_when_text_grows(head: str, tail: str) -> None:
    assert estimate_tokens(head + tail) >= estimate_tokens(head)
    assert estimate_tokens(head + tail) <= estimate_tokens(head) + estimate_tokens(tail) + 1


def test_rounds_ask_to_conclude_after_the_fourth_and_end_tools_at_the_tenth() -> None:
    assert round_policy(SOFT_ROUNDS).conclude is False
    assert round_policy(SOFT_ROUNDS + 1).conclude is True
    assert round_policy(HARD_ROUNDS - 1).tools is True
    assert round_policy(HARD_ROUNDS).tools is False


@given(st.lists(st.integers(min_value=0, max_value=3_000), max_size=40))
def test_the_recent_window_is_the_newest_run_within_the_cap(tokens: list[int]) -> None:
    taken = recent_window(tokens, 5_000)

    assert sum(tokens[:taken]) <= 5_000
    assert taken == len(tokens) or sum(tokens[: taken + 1]) > 5_000
    assert needs_compaction(3_501)
    assert not needs_compaction(3_500)


def source(number: int, locator: str | None = None) -> SourceRef:
    return SourceRef(SourceKind.MEETING, f"m-{number}", f"Meeting {number}", locator=locator)


@given(st.lists(st.lists(st.integers(min_value=0, max_value=80), max_size=10), max_size=12))
def test_a_source_keeps_its_number_for_the_whole_run(batches: list[list[int]]) -> None:
    ledger = SourceLedger()
    given_numbers: dict[str, int] = {}
    for batch in batches:
        ledger, numbers = ledger.add(source(n) for n in batch)
        for n, number in zip(batch, numbers, strict=True):
            if number is None:
                assert len(ledger.sources) == SOURCES_MAX
                continue
            assert given_numbers.setdefault(f"m-{n}", number) == number
            assert ledger.sources[number - 1].id == f"m-{n}"


def test_another_place_in_the_same_meeting_is_another_source() -> None:
    _, numbers = SourceLedger().add([source(1, "01:00"), source(1, "02:00"), source(1, "01:00")])

    assert numbers == (1, 2, 1)

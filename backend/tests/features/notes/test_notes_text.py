"""The transcript as the model reads it, its answers and the stored write-up (notes step 6)."""

import uuid
from itertools import pairwise

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.core.config.gate import UnsafeConfigurationError, enforce_production_gate
from shosai.core.config.loading import load_settings
from shosai.features.notes.application.found_items import (
    kept_by_merge,
    owner_of,
    raw_findings,
    without_repeats,
)
from shosai.features.notes.application.notes_model import json_object_of
from shosai.features.notes.domain.findings import Evidence, Finding, FindingKind
from shosai.features.notes.domain.templates import (
    LEO_LAYOUT,
    SectionKind,
    TemplateSection,
    builtin,
)
from shosai.features.notes.domain.transcript_text import (
    OVERLAP_LINES,
    SpokenLine,
    clock,
    numbered,
    rendered,
    span,
    tail,
    windows,
)
from shosai.features.notes.domain.write_up import (
    ListedFinding,
    SectionPlan,
    builtin_layout,
    layout_from_json,
    layout_json,
    own_layout,
    written_sections,
)
from shosai.features.notes.infrastructure.prompts import FindingsAnswer, FoundItem
from shosai.features.notes.settings import NotesSettings, notes_model_set
from tests.core.config.sample_environ import local_environ, production_environ

texts = st.text(alphabet="абвгд efgh.,?", min_size=1, max_size=120)


def spoken(texts_: list[str]) -> list[SpokenLine]:
    return numbered([(n * 1000, 900, n % 3, text) for n, text in enumerate(texts_)])


def cost(line: SpokenLine) -> int:
    return len(rendered(line)) + 1


@given(st.lists(texts, min_size=1, max_size=80), st.integers(min_value=40, max_value=2000))
def test_windows_hold_whole_lines_within_the_budget_and_overlap_by_eight(
    raw: list[str], budget: int
) -> None:
    lines = spoken(raw)

    parts = windows(lines, budget)

    assert parts[0][0] == lines[0]
    assert parts[-1][-1] == lines[-1]
    assert {line.number for part in parts for line in part} == {line.number for line in lines}
    for part in parts:
        assert len(part) == 1 or sum(map(cost, part)) <= budget
        assert [line.number for line in part] == list(range(part[0].number, part[-1].number + 1))
    for before, after in pairwise(parts):
        shared = before[-1].number - after[0].number + 1
        assert shared == min(OVERLAP_LINES, len(before) - 1)


@given(st.lists(texts, min_size=1, max_size=80), st.integers(min_value=0, max_value=3000))
def test_the_tail_is_the_longest_run_of_closing_lines_within_the_budget(
    raw: list[str], budget: int
) -> None:
    lines = spoken(raw)

    kept = tail(lines, budget)

    assert kept == lines[len(lines) - len(kept) :]
    assert len(kept) == 1 or sum(map(cost, kept)) <= budget
    if len(kept) < len(lines):
        assert sum(map(cost, lines[-len(kept) - 1 :])) > budget


def test_a_line_reads_with_its_number_time_and_speaker_and_a_span_needs_both_lines() -> None:
    lines = numbered([(0, 1500, 0, "Начнём."), (3_725_000, 2000, None, "Итак.")])

    assert [rendered(line) for line in lines] == [
        "L1 [00:00] S1: Начнём.",
        "L2 [1:02:05] S?: Итак.",
    ]
    assert clock(59_999) == "00:59"
    assert span(lines, 1, 2) == (0, 3_727_000)
    assert span(lines, 2, 1) is None
    assert span(lines, 1, 3) is None


def test_an_answer_is_read_from_its_json_object_fence_or_not() -> None:
    fenced = '```json\n{"findings": [{"kind": "risk", "text": "Сроки", "first_line": 1, ' + (
        '"last_line": 1}]}\n```'
    )

    assert json_object_of(fenced, FindingsAnswer) is not None
    assert json_object_of("", FindingsAnswer) is None
    assert json_object_of('{"findings": "none"}', FindingsAnswer) is None
    assert json_object_of("I found nothing.", FindingsAnswer) is None


def test_findings_cite_lines_of_their_window_and_name_owners_by_label_or_name() -> None:
    window = spoken(["Решили.", "Сделаю к пятнице.", "Риск по срокам."])
    items = [
        FoundItem(kind="decision", text="Решили", first_line=1, last_line=1),
        FoundItem(kind="Action_Item ", text="Сделать", owner="S2", first_line=2, last_line=2),
        FoundItem(kind="promise", text="Обещал", owner="Анна", first_line=2, last_line=3),
        FoundItem(kind="idea", text="Неизвестный вид", first_line=1, last_line=1),
        FoundItem(kind="risk", text="Выдумана строка", first_line=3, last_line=9),
    ]

    found = list(raw_findings(items, window))

    assert [(f.kind, f.start_ms, f.end_ms) for f in found] == [
        (FindingKind.DECISION, 0, 900),
        (FindingKind.ACTION_ITEM, 1000, 1900),
        (FindingKind.PROMISE, 1000, 2900),
    ]
    assert [(f.owner_speaker, f.owner_name) for f in found] == [
        (None, None),
        (1, None),
        (None, "Анна"),
    ]
    assert owner_of("S0") == (None, "S0")
    assert owner_of("  ") == (None, None)


def test_repeats_of_overlapping_windows_are_kept_once_and_a_merge_keeps_its_numbers() -> None:
    first = Finding(FindingKind.DECISION, "Запускаем", Evidence(1000, 2000, ""))
    again = Finding(FindingKind.DECISION, "запускаем", Evidence(1000, 2000, ""))
    other = Finding(FindingKind.RISK, "Сроки", Evidence(500, 900, ""))

    kept = without_repeats([first, again, other])

    assert kept == [other, first]
    assert kept_by_merge(kept, [2, 2, 7]) == [first]
    assert kept_by_merge(kept, [0]) == kept


def test_sections_list_findings_by_kind_and_a_layout_survives_its_copy() -> None:
    shipped = builtin("oneOnOne")
    assert shipped is not None
    layout = builtin_layout(shipped)
    own = own_layout(
        [TemplateSection(SectionKind.SUMMARY, "Итог"), TemplateSection(SectionKind.DECISIONS)]
    )
    decision, action = uuid.uuid4(), uuid.uuid4()
    listed = [
        ListedFinding(decision, FindingKind.DECISION),
        ListedFinding(action, FindingKind.ACTION_ITEM),
    ]

    sections = written_sections(layout, "Коротко.", listed)

    assert sections == [
        {"kind": "summary", "heading_code": "howItsGoing", "text": "Коротко."},
        {"kind": "key_points", "heading_code": "topics", "finding_ids": []},
        {"kind": "action_items", "heading_code": "nextSteps", "finding_ids": [str(action)]},
    ]
    assert own == (
        SectionPlan(SectionKind.SUMMARY, title="Итог"),
        SectionPlan(SectionKind.DECISIONS, heading_code="decisions"),
    )
    assert layout_from_json(layout_json(own)) == own
    assert len(builtin_layout(LEO_LAYOUT)) == 4
    with pytest.raises(ValueError, match="секций"):
        layout_from_json([])


def test_production_needs_the_notes_model_and_development_may_go_without() -> None:
    environ = production_environ()
    del environ["NOTES_MODEL"]

    with pytest.raises(UnsafeConfigurationError) as raised:
        enforce_production_gate(load_settings(environ, [NotesSettings]), [notes_model_set])
    enforce_production_gate(load_settings(production_environ(), [NotesSettings]), [notes_model_set])
    local = load_settings(local_environ(), [NotesSettings]).features.get(NotesSettings)

    assert [v.setting for v in raised.value.violations] == ["NOTES_MODEL"]
    assert local.notes_model is None

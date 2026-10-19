"""Templates, findings and the mind map (meetings plan step 1)."""

from datetime import UTC, date, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.meetings.domain.findings import (
    Evidence,
    Finding,
    FindingKind,
    RawFinding,
    checked_due,
    checked_finding,
)
from shosai.features.meetings.domain.mind_map import (
    CHILDREN_MAX,
    CHILDREN_MIN,
    TOPICS_MAX,
    project_map,
)
from shosai.features.meetings.domain.templates import (
    BUILTIN_TEMPLATES,
    ENHANCED,
    SECTION_ORDER,
    TEMPLATES_MAX,
    SectionKind,
    TemplateIcon,
    TemplateRule,
    TemplateRuleError,
    TemplateSection,
    builtin,
    checked_template,
    may_add_template,
)

START = datetime(2026, 10, 19, 9, tzinfo=UTC)
CABINET_IDS = {
    "catchUpInvestor", "catchUpPortfolio", "lpProspective", "vcBoardMeeting",
    "vcPitch", "oneOnOne", "customerCall", "teamSync",
}  # fmt: skip


def test_the_shipped_templates_are_the_cabinets_eight_in_section_order() -> None:
    assert {template.template_id for template in BUILTIN_TEMPLATES} == CABINET_IDS
    for template in BUILTIN_TEMPLATES:
        kinds = [section.kind for section in template.sections]
        assert kinds == sorted(kinds, key=SECTION_ORDER.index)
        assert len(set(kinds)) == len(kinds)
    leo = builtin(ENHANCED)
    assert leo is not None
    assert [s.kind for s in leo.sections] == list(SECTION_ORDER)
    assert builtin("mine") is None


@given(kinds=st.lists(st.sampled_from(list(SectionKind)), min_size=1, max_size=4, unique=True))
def test_a_persons_template_keeps_its_sections_in_the_fixed_order(kinds: list[SectionKind]) -> None:
    draft = checked_template(
        " Совет ", "", TemplateIcon.ROCKET, [TemplateSection(kind, " ") for kind in kinds]
    )

    assert draft.name == "Совет"
    assert draft.description is None
    assert [s.kind for s in draft.sections] == [k for k in SECTION_ORDER if k in kinds]
    assert all(section.title is None for section in draft.sections)


@pytest.mark.parametrize(
    ("name", "description", "sections", "rule"),
    [
        (" ", None, [TemplateSection(SectionKind.SUMMARY)], TemplateRule.NAME_REQUIRED),
        ("n" * 61, None, [TemplateSection(SectionKind.SUMMARY)], TemplateRule.NAME_TOO_LONG),
        ("n", "d" * 121, [TemplateSection(SectionKind.SUMMARY)], TemplateRule.DESCRIPTION_TOO_LONG),
        ("n", None, [], TemplateRule.SECTIONS_REQUIRED),
        ("n", None, [TemplateSection(SectionKind.SUMMARY)] * 2, TemplateRule.SECTION_REPEATED),
        (
            "n",
            None,
            [TemplateSection(SectionKind.DECISIONS, "t" * 41)],
            TemplateRule.SECTION_TITLE_TOO_LONG,
        ),
    ],
)
def test_a_template_that_breaks_a_rule_is_refused_with_its_code(
    name: str, description: str | None, sections: list[TemplateSection], rule: TemplateRule
) -> None:
    with pytest.raises(TemplateRuleError) as raised:
        checked_template(name, description, TemplateIcon.CHART, sections)

    assert raised.value.code == rule.value


def test_a_person_keeps_at_most_fifty_templates() -> None:
    assert may_add_template(TEMPLATES_MAX - 1)
    assert not may_add_template(TEMPLATES_MAX)


@given(
    start=st.integers(-1_000, 4_000_000),
    length=st.integers(-1_000, 4_000_000),
    meeting_ms=st.integers(0, 3_600_000),
    text=st.text(max_size=600),
)
def test_every_kept_finding_has_text_and_evidence_inside_the_meeting(
    start: int, length: int, meeting_ms: int, text: str
) -> None:
    raw = RawFinding(FindingKind.DECISION, text, start, start + length, quote="«так и сделаем»")

    finding = checked_finding(raw, meeting_ms=meeting_ms, meeting_started_at=START)

    if finding is not None:
        assert finding.text.strip()
        assert len(finding.text) <= 500
        assert 0 <= finding.evidence.start_ms <= finding.evidence.end_ms <= meeting_ms


def test_a_due_date_is_kept_from_the_meetings_day_up_to_a_year() -> None:
    assert checked_due("2026-10-24", START) == date(2026, 10, 24)
    assert checked_due("2026-10-18", START) is None
    assert checked_due("2028-01-01", START) is None
    assert checked_due("пятница", START) is None


def finding(topic: str | None, start_ms: int) -> Finding:
    return Finding(
        FindingKind.KEY_POINT, f"пункт {start_ms}", Evidence(start_ms, start_ms, ""), topic
    )


@given(topics=st.lists(st.none() | st.sampled_from("abcdefghij"), max_size=60))
def test_the_map_has_one_root_and_topics_of_two_to_five_findings(topics: list[str | None]) -> None:
    findings = [finding(topic, at) for at, topic in enumerate(topics)]
    counts = {t: topics.count(t) for t in set(topics) if t is not None}

    root = project_map("Встреча", findings)

    assert root.label == "Встреча"
    assert len(root.children) <= TOPICS_MAX
    assert all(CHILDREN_MIN <= len(t.children) <= CHILDREN_MAX for t in root.children)
    assert all(not child.children for t in root.children for child in t.children)
    if sum(1 for count in counts.values() if count >= CHILDREN_MIN) >= 3:
        assert 3 <= len(root.children) <= TOPICS_MAX


def test_the_map_keeps_the_largest_topics_in_the_order_they_came_up() -> None:
    topics = ["a", "b", "c", "d", "e", "f", "g"] * 2 + ["g", "a"]
    root = project_map("М", [finding(topic, at) for at, topic in enumerate(topics)])

    assert [topic.label for topic in root.children] == ["a", "b", "c", "d", "e", "g"]

"""What becomes of an extracted statement: confirmations, refusals, the rule and the policy
(Leo §6.2-§6.3, ADR 0071 MM-D1, MM-D5)."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.memory.domain.admission import (
    CANDIDATES_PER_DAY,
    PROBE_EVERY,
    SAME_SUBJECT,
    Admission,
    Judgement,
    Neighbour,
    PolicyAnswer,
    Statement,
    before_judge,
    by_policy,
    by_rule,
    is_probe,
    same_words,
    subject_fact,
)
from shosai.features.memory.domain.facts import (
    SPOKEN_SOURCES,
    EndReason,
    FactKind,
    FactStatus,
    SourceKind,
)
from tests.features.memory.facts_kit import NOW, fact, kinds, sources

ADMITTING = [source for source in SourceKind if source is not SourceKind.IMPORTED]
statements = st.builds(
    Statement,
    text=st.just("Prefers short answers"),
    kind=kinds,
    explicit=st.booleans(),
    sensitive=st.booleans(),
    about_person=st.booleans(),
)
answers = st.builds(
    PolicyAnswer,
    judgement=st.sampled_from(Judgement),
    replaces=st.none() | st.uuids(),
    probe=st.booleans(),
)
admitting = st.sampled_from(ADMITTING)
counts = st.integers(0, 10)


@given(statements, admitting, counts)
def test_the_rule_never_saves_a_guess(statement: Statement, source: SourceKind, today: int) -> None:
    admit = by_rule(statement, source, today)
    if admit.admission is Admission.ACTIVE:
        assert statement.explicit
        assert source in SPOKEN_SOURCES
        assert admit.confirmed
    else:
        assert admit.admission in {Admission.CANDIDATE, Admission.SKIPPED_CAP}


@given(statements, admitting, answers, counts)
def test_the_policy_is_never_less_careful_than_the_rule(
    statement: Statement, source: SourceKind, answer: PolicyAnswer, today: int
) -> None:
    admit = by_policy(statement, source, answer, today)
    if admit.admission is Admission.AUTO_SAVED:
        assert not statement.sensitive
        assert not answer.probe
        assert source in SPOKEN_SOURCES
        assert answer.judgement in {Judgement.STORE, Judgement.SUPERSEDE}
        assert not admit.confirmed
    if admit.admission is Admission.ACTIVE:
        assert by_rule(statement, source, today).admission is Admission.ACTIVE
    if source is SourceKind.MEETING:
        assert admit.admission in {
            Admission.CANDIDATE,
            Admission.SKIPPED_CAP,
            Admission.SKIPPED_JUDGE,
        }
    if admit.supersedes:
        assert admit.neighbour == answer.replaces is not None


@given(statements, admitting, st.one_of(answers.map(lambda a: (a,)), st.just(())))
def test_no_more_than_three_new_candidates_a_day(
    statement: Statement, source: SourceKind, answer: tuple[PolicyAnswer, ...]
) -> None:
    for today in range(CANDIDATES_PER_DAY, CANDIDATES_PER_DAY + 3):
        admit = (
            by_policy(statement, source, answer[0], today)
            if answer
            else by_rule(statement, source, today)
        )
        assert admit.admission is not Admission.CANDIDATE


def test_only_the_same_words_confirm_a_held_fact() -> None:
    held = fact(statement="Is vegetarian")
    near = [Neighbour(fact(), 0.5), Neighbour(held, 0.95)]
    same = Statement(
        "is  vegetarian.", FactKind.FACT, explicit=False, sensitive=False, about_person=True
    )
    admit = before_judge(same, SourceKind.USER_STATEMENT, near, NOW)
    assert admit is not None
    assert (admit.admission, admit.neighbour) == (Admission.CONFIRMED, held.id)
    # Противоречие той же темы похоже не меньше перефразировки: подтверждением оно не считается.
    moved = Statement("Is vegan", FactKind.FACT, explicit=False, sensitive=False, about_person=True)
    assert before_judge(moved, SourceKind.USER_STATEMENT, near, NOW) is None
    assert subject_fact(near) == held.id
    assert by_rule(moved, SourceKind.USER_STATEMENT, 0, subject_fact(near)).neighbour == held.id


@pytest.mark.parametrize(
    ("first", "second", "same"),
    [
        ("Живёт в Москве", "живёт в москве!", True),
        ("東京に住んでいる", "東京に住んでいる。", True),
        ("Vive en Madrid", "Vive  en\u00a0Madrid", True),
        ("يعيش في القاهرة", "يعيش في الإسكندرية", False),
        ("Lives in Moscow", "Lives in Berlin", False),
    ],
)
def test_the_same_words_hold_in_any_script(first: str, second: str, *, same: bool) -> None:
    assert same_words(first, second) is same


def test_a_waiting_statement_is_not_asked_twice() -> None:
    waiting = fact(status=FactStatus.CANDIDATE)
    statement = Statement("x", FactKind.FACT, explicit=True, sensitive=False, about_person=True)
    admit = before_judge(statement, SourceKind.USER_STATEMENT, [Neighbour(waiting, 0.95)], NOW)
    assert admit is not None
    assert admit.admission is Admission.SKIPPED_PENDING


def test_what_the_person_refused_is_never_asked_again_unless_asked_for() -> None:
    refused = fact(status=FactStatus.FORGOTTEN, ended_reason=EndReason.TURNED_DOWN, ended_at=NOW)
    near = [Neighbour(refused, 0.97)]
    plain = Statement("x", FactKind.FACT, explicit=False, sensitive=False, about_person=True)
    admit = before_judge(plain, SourceKind.USER_STATEMENT, near, NOW + timedelta(days=30))
    assert admit is not None
    assert admit.admission is Admission.SKIPPED_FORGOTTEN
    asked = Statement("x", FactKind.FACT, explicit=True, sensitive=False, about_person=True)
    assert before_judge(asked, SourceKind.USER_STATEMENT, near, NOW) is None
    assert before_judge(plain, SourceKind.USER_STATEMENT, near, NOW + timedelta(days=181)) is None
    faded = fact(status=FactStatus.FORGOTTEN, ended_reason=EndReason.EXPIRED, ended_at=NOW)
    assert before_judge(plain, SourceKind.USER_STATEMENT, [Neighbour(faded, 0.99)], NOW) is None


def test_a_neighbour_on_another_subject_decides_nothing() -> None:
    statement = Statement("x", FactKind.FACT, explicit=False, sensitive=False, about_person=True)
    near = [Neighbour(fact(statement="x"), SAME_SUBJECT - 0.01)]
    assert before_judge(statement, SourceKind.USER_STATEMENT, near, NOW) is None
    assert subject_fact(near) is None


@given(sources)
def test_an_explicit_request_supersedes_only_when_the_policy_names_a_fact(
    source: SourceKind,
) -> None:
    statement = Statement("x", FactKind.FACT, explicit=True, sensitive=True, about_person=True)
    old = uuid4()
    admit = by_policy(statement, source, PolicyAnswer(Judgement.SUPERSEDE, old, probe=False), 0)
    if source in SPOKEN_SOURCES:
        assert (admit.admission, admit.neighbour, admit.supersedes) == (
            Admission.ACTIVE,
            old,
            True,
        )
    unnamed = by_policy(statement, source, PolicyAnswer(Judgement.SUPERSEDE, None, probe=False), 0)
    assert not unnamed.supersedes


def test_one_statement_in_twenty_is_a_probe() -> None:
    probes = sum(is_probe(UUID(int=n)) for n in range(PROBE_EVERY * 50))
    assert probes == 50

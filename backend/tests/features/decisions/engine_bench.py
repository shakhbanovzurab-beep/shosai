"""Doubles around the Decision Layer's engine: Jev, the stored policies, the terms, the records."""

import asyncio
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from prometheus_client import CollectorRegistry

from shosai.core.agent_tools.spec import Reversibility
from shosai.core.ai.calls import CallContext, ModelRef, ModelRoute, Provider
from shosai.core.ai.decisions import Answer, Decision, DecisionRequest, NoulAnswer, ScoreAnswer
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.results import Usage
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.decisions.application.asking import Asker
from shosai.features.decisions.application.engine import DecisionEngine
from shosai.features.decisions.application.in_force import PoliciesInForce, StoredPolicy
from shosai.features.decisions.application.recording import Recorder
from shosai.features.decisions.contracts import CardFacts, CardFriction, DecisionCall
from shosai.features.decisions.domain.outcomes import Subject, SubjectKind
from shosai.features.decisions.domain.policies import policies_by_key
from shosai.features.decisions.domain.policy import Policy
from shosai.features.decisions.domain.verdicts import Cut
from shosai.features.decisions.infrastructure.metrics import DecisionMetrics

JEV = ModelRef(Provider.OPENROUTER, "typesafe/jev-1.13")
NOW = datetime(2026, 10, 27, 9, tzinfo=UTC)
FRICTION_CUTS = {"matches": Cut(lower=0.5, upper=0.6), "wide": Cut(lower=0.4, upper=0.5)}


@dataclass
class ScriptedJev:
    """Jev as the port: answers, a delay, or a failure; every request kept."""

    answers: Mapping[str, Answer] = field(default_factory=dict)
    delay: timedelta = timedelta(0)
    failure: AiFailure | None = None
    asked: list[tuple[CallContext, DecisionRequest]] = field(default_factory=list)

    async def decide(
        self, context: CallContext, route: ModelRoute, request: DecisionRequest
    ) -> Decision:
        """The scripted answer to every question asked, after the delay."""
        self.asked.append((context, request))
        await asyncio.sleep(self.delay.total_seconds())
        if self.failure is not None:
            raise AiCallError(self.failure)
        picked = {name: self.answers[name] for name in request.questions if name in self.answers}
        return Decision(picked, JEV, "typesafe/jev-1.13-20260917", "gen-1", Usage(input_tokens=600))


@dataclass
class Store:
    """The versions in force as a test sets them."""

    stored: list[StoredPolicy] = field(default_factory=list)

    async def in_force(self) -> Sequence[StoredPolicy]:
        """What the test stored."""
        return list(self.stored)


@dataclass
class Terms:
    """Whether Jev's endpoint keeps nothing, as the test says."""

    keeps_nothing: bool = True

    async def zero_retention(self) -> bool:
        """The test's answer."""
        return self.keeps_nothing


@dataclass
class Rows:
    """The rows the engine would write, by home."""

    decisions: list[tuple[Home, dict[str, Any]]] = field(default_factory=list)
    outcomes: list[tuple[Home, dict[str, Any]]] = field(default_factory=list)

    def add_decision(self, home: Home, row: dict[str, Any]) -> None:
        """Keep a decision's row."""
        self.decisions.append((home, row))

    def add_outcome(self, home: Home, row: dict[str, Any]) -> None:
        """Keep an outcome's row."""
        self.outcomes.append((home, row))


@dataclass
class Bench:
    """An engine over doubles, and what a test inspects."""

    engine: DecisionEngine
    jev: ScriptedJev
    store: Store
    terms: Terms
    rows: Rows
    registry: CollectorRegistry
    spans: InMemorySpanExporter

    def sample(self, name: str, **labels: str) -> float:
        """A metric's value, 0 when absent."""
        return self.registry.get_sample_value(name, labels) or 0.0


def stored(
    policy: Policy[Any, Any], state: str, cuts: Mapping[str, Cut], revision: int = 1
) -> StoredPolicy:
    """A version in force as the EU home keeps it."""
    return StoredPolicy(policy.point, policy.version, state, revision, policy.digest(), cuts)


def bench(
    *stored_policies: StoredPolicy,
    max_in_flight: int = 8,
    known: Sequence[Policy[Any, Any]] = (),
) -> Bench:
    """An engine whose versions in force are `stored_policies`; `known` adds versions the
    code has beyond this image's, as a later image would."""
    registry = CollectorRegistry()
    metrics = DecisionMetrics(registry)
    jev, store, terms, rows = ScriptedJev(), Store(list(stored_policies)), Terms(), Rows()
    spans = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(spans))
    recorder = Recorder(rows, terms, metrics, lambda: NOW, b"state-key")
    engine = DecisionEngine(
        (
            PoliciesInForce(store, policies_by_key() | {p.key: p for p in known}),
            Asker(jev, ModelRoute(JEV)),
            recorder,
        ),
        (metrics, provider.get_tracer("test")),
        max_in_flight=max_in_flight,
    )
    return Bench(engine, jev, store, terms, rows, registry, spans)


def card_call(
    rule: CardFriction = CardFriction.STANDARD,
    *,
    home: Home = Home.EU,
    consent: bool = True,
    reversibility: Reversibility = Reversibility.REVERSIBLE,
) -> DecisionCall[CardFacts, CardFriction]:
    """A friction decision for one person's card."""
    facts = CardFacts(
        tool="tasks.create", toolset="tasks", reversibility=reversibility, items=2,
        other_space=False, rounds=1, request="Создай две задачи на завтра",
        card="Создать задачи: «Отчёт», «Звонок»",
    )  # fmt: skip
    subject = Subject(SubjectKind.ACTION, uuid.uuid4())
    scope = TenancyScope(home, uuid.uuid4())
    return DecisionCall(scope, consent, subject, facts, rule, "ru")


def matching(*, narrow: bool = True) -> dict[str, Answer]:
    """Jev's answers to friction: the action matches; narrow or wide."""
    levels = (
        {"0": 0.9, "1": 0.1, "2": 0.0, "3": 0.0}
        if narrow
        else {"0": 0.0, "1": 0.1, "2": 0.6, "3": 0.3}
    )
    return {
        "matches_request": NoulAnswer(0.95),
        "reach": ScoreAnswer(0.1 if narrow else 2.2, 0.9, levels),
    }

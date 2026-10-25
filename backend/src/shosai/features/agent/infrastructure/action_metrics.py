"""Leo's actions in numbers (Leo §11.3; agent step 9a): closed label sets, no ids, no text.

`shosai_agent_actions_total{origin, outcome}` counts actions by how they ended — succeeded,
failed, rejected, expired and the rest of the state machine's ends; `shosai_agent_approval_seconds`
is how long the person took from the card to the approval, and
`shosai_agent_action_execution_seconds` from the approval to the action's end. The objective
on approved actions — carried out or refused with a code within 30 s — reads
`shosai_agent_approved_actions_total{result}`: `in_time`, `late`, or `unknown` when nobody can
tell whether the change took effect. The hourly check of L-N5 sets, per home, the items
executed twice (`shosai_agent_items_executed_twice`) and executed without an approval
(`shosai_agent_items_executed_unapproved`); both must stay 0.
"""

from typing import Final

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

from shosai.core.kernel.homes import Home

APPROVED_ACTIONS: Final = "shosai_agent_approved_actions_total"
EXECUTED_TWICE: Final = "shosai_agent_items_executed_twice"
EXECUTED_UNAPPROVED: Final = "shosai_agent_items_executed_unapproved"
# Цель на одобренные действия (§16.3): исполнено или отказано с кодом за 30 с.
IN_TIME_SECONDS: Final = 30.0
UNKNOWN_OUTCOME: Final = "outcome_unknown"
APPROVAL_BUCKETS: Final = (1, 5, 15, 30, 60, 120, 300, 900, 1800, 3600)
EXECUTION_BUCKETS: Final = (0.25, 0.5, 1, 2.5, 5, 10, 20, 30, 60, 120)


class ActionMetrics:
    """The actions' counters and times, in the process's registry."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._actions = Counter(
            "shosai_agent_actions",
            "Действия Leo по источнику и исходу",
            ("origin", "outcome"),
            registry=registry,
        )
        self._approval = Histogram(
            "shosai_agent_approval_seconds",
            "Время от карточки до одобрения человеком",
            buckets=APPROVAL_BUCKETS,
            registry=registry,
        )
        self._execution = Histogram(
            "shosai_agent_action_execution_seconds",
            "Время от одобрения до конца действия: исполнено, отказ или исход неизвестен",
            buckets=EXECUTION_BUCKETS,
            registry=registry,
        )
        self._approved_ends = Counter(
            APPROVED_ACTIONS.removesuffix("_total"),
            "Одобренные действия Leo: исполнены или отказаны за 30 с, позже, или исход неизвестен",
            ("result",),
            registry=registry,
        )
        self._twice = Gauge(
            EXECUTED_TWICE,
            "Пункты действий Leo, исполненные дважды за два последних часа (L-N5)",
            ("home",),
            registry=registry,
        )
        self._unapproved = Gauge(
            EXECUTED_UNAPPROVED,
            "Пункты действий Leo, исполненные без одобрения за два последних часа (L-N5)",
            ("home",),
            registry=registry,
        )

    def decided(self, origin: str, outcome: str) -> None:
        """An action ended with its outcome."""
        self._actions.labels(origin=origin, outcome=outcome).inc()

    def approved(self, seconds: float) -> None:
        """The person approved a card `seconds` after it was proposed."""
        self._approval.observe(max(seconds, 0.0))

    def ended_after_approval(self, status: str, seconds: float) -> None:
        """An approved action ended with `status`, `seconds` after its approval."""
        waited = max(seconds, 0.0)
        self._execution.observe(waited)
        result = (
            "unknown" if status == UNKNOWN_OUTCOME
            else "in_time" if waited <= IN_TIME_SECONDS
            else "late"
        )  # fmt: skip
        self._approved_ends.labels(result=result).inc()

    def invariants(self, home: Home, twice: int, unapproved: int) -> None:
        """The home's items executed twice and executed without an approval, as last checked."""
        self._twice.labels(home=home.value).set(twice)
        self._unapproved.labels(home=home.value).set(unapproved)

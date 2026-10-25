"""An action Leo proposes and its one path to taking effect (Leo §8.4, ADR 0025).

An action is proposed with the exact targets its slices planned; the person approves or
rejects it, or it expires; an approved one is claimed for execution once and ends with the
outcome of its items, or `outcome_unknown` when an item was cut mid-effect — never retried.
Each transition names the status it expects, so the store applies it as one conditional
update and concurrent attempts — two tabs, a double click — have exactly one winner. The
cabinet's card shows a public status: an approved action is already `executing` to it, and a
superseded one reads as expired.
"""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final

INTERACTIVE_EXPIRY: Final = timedelta(hours=1)
ITEMS_MAX: Final = 20
NONCE_BYTES: Final = 16


class ActionStatus(StrEnum):
    """Where an action stands (Leo §8.4)."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    OUTCOME_UNKNOWN = "outcome_unknown"
    REJECTED = "rejected"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


TERMINAL: Final = frozenset(
    {
        ActionStatus.SUCCEEDED,
        ActionStatus.PARTIALLY_SUCCEEDED,
        ActionStatus.FAILED,
        ActionStatus.OUTCOME_UNKNOWN,
        ActionStatus.REJECTED,
        ActionStatus.EXPIRED,
        ActionStatus.SUPERSEDED,
    }
)


class ActionEvent(StrEnum):
    """What happens to an action."""

    APPROVE = "approve"
    REJECT = "reject"
    EXPIRE = "expire"
    # Тред удалён, человек отозвал повод: карточку уже нельзя одобрить.
    SUPERSEDE = "supersede"
    CLAIM = "claim"
    SUCCEED = "succeed"
    SUCCEED_PARTLY = "succeed_partly"
    FAIL = "fail"
    LOSE = "lose"


@dataclass(frozen=True, slots=True)
class Transition:
    """One conditional update: from the status it expects to the status it writes."""

    expected: ActionStatus
    to: ActionStatus


_TRANSITIONS: Final[dict[tuple[ActionStatus, ActionEvent], ActionStatus]] = {
    (ActionStatus.PROPOSED, ActionEvent.APPROVE): ActionStatus.APPROVED,
    (ActionStatus.PROPOSED, ActionEvent.REJECT): ActionStatus.REJECTED,
    (ActionStatus.PROPOSED, ActionEvent.EXPIRE): ActionStatus.EXPIRED,
    (ActionStatus.PROPOSED, ActionEvent.SUPERSEDE): ActionStatus.SUPERSEDED,
    (ActionStatus.APPROVED, ActionEvent.CLAIM): ActionStatus.EXECUTING,
    (ActionStatus.EXECUTING, ActionEvent.SUCCEED): ActionStatus.SUCCEEDED,
    (ActionStatus.EXECUTING, ActionEvent.SUCCEED_PARTLY): ActionStatus.PARTIALLY_SUCCEEDED,
    (ActionStatus.EXECUTING, ActionEvent.FAIL): ActionStatus.FAILED,
    (ActionStatus.EXECUTING, ActionEvent.LOSE): ActionStatus.OUTCOME_UNKNOWN,
    # Исполнитель не взял одобренное (процесс упал до захвата): исход неизвестен, не повтор.
    (ActionStatus.APPROVED, ActionEvent.LOSE): ActionStatus.OUTCOME_UNKNOWN,
    # Одобренное так и не взяли за отведённое время: ничего не начиналось — это отказ.
    (ActionStatus.APPROVED, ActionEvent.FAIL): ActionStatus.FAILED,
}


class ActionTransitionError(ValueError):
    """The event does not apply to the action in its status."""


def transition(current: ActionStatus, event: ActionEvent) -> Transition:
    """The conditional update the event makes; an ended action accepts nothing."""
    status = _TRANSITIONS.get((current, event))
    if status is None:
        message = f"действие в статусе {current} не принимает событие {event}"
        raise ActionTransitionError(message)
    return Transition(current, status)


class ItemOutcome(StrEnum):
    """How one item of an approved action ended."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    OUTCOME_UNKNOWN = "outcome_unknown"


def finishing_event(outcomes: Collection[ItemOutcome]) -> ActionEvent:
    """How the action ends from its items' outcomes: honest partial success, never atomic."""
    if not outcomes or ItemOutcome.PENDING in outcomes:
        message = "действие завершается, когда исход есть у каждого пункта"
        raise ActionTransitionError(message)
    if ItemOutcome.OUTCOME_UNKNOWN in outcomes:
        return ActionEvent.LOSE
    succeeded = sum(outcome is ItemOutcome.SUCCEEDED for outcome in outcomes)
    if succeeded == len(outcomes):
        return ActionEvent.SUCCEED
    return ActionEvent.SUCCEED_PARTLY if succeeded else ActionEvent.FAIL


class AuditEvent(StrEnum):
    """What an action's audit row records (`agent_audit.event`)."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"
    # Пункт подействовал: строку пишет событие среза `agent.action_item.executed`.
    EXECUTED = "executed"
    FAILED = "failed"
    OUTCOME_UNKNOWN = "outcome_unknown"


class ProposalOrigin(StrEnum):
    """Where a proposal came from."""

    # Ход Leo в треде.
    TURN = "turn"
    # Запланировал срез без хода модели (AG-R2): «Сделать задачей» из дайджеста.
    PROPOSAL_PORT = "proposal_port"


class ApprovedVia(StrEnum):
    """Where the person approved."""

    WEB = "web"
    INBOX = "inbox"


class PublicStatus(StrEnum):
    """The status the cabinet's card shows (`LeoProposal.status`)."""

    PROPOSED = "proposed"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    OUTCOME_UNKNOWN = "outcome_unknown"


_PUBLIC: Final[dict[ActionStatus, PublicStatus]] = {
    ActionStatus.APPROVED: PublicStatus.EXECUTING,
    ActionStatus.SUPERSEDED: PublicStatus.EXPIRED,
}


def public_status(status: ActionStatus) -> PublicStatus:
    """What the card shows for the stored status."""
    return _PUBLIC.get(status) or PublicStatus(status.value)


def internal_statuses(public: PublicStatus) -> tuple[str, ...]:
    """The stored statuses a card of the public one may have."""
    return tuple(status.value for status in ActionStatus if public_status(status) is public)


def expires_at(created_at: datetime, origin: ProposalOrigin) -> datetime:
    """When a proposal can no longer be approved: an hour for every origin built so far."""
    match origin:
        case ProposalOrigin.TURN | ProposalOrigin.PROPOSAL_PORT:
            return created_at + INTERACTIVE_EXPIRY


def approvable(status: ActionStatus, expiry: datetime, now: datetime) -> bool:
    """Whether the person may still approve: proposed and not past its expiry."""
    return status is ActionStatus.PROPOSED and now < expiry


def item_key(action_id: str, index: int) -> str:
    """The idempotency key of an item: the action and its place in it (Leo §8.4 rule 2)."""
    if index < 0 or index >= ITEMS_MAX:
        message = f"пункт действия — от 0 до {ITEMS_MAX - 1}"
        raise ValueError(message)
    return f"{action_id}:{index}"

"""How carefully a card asks for approval (Leo §6.3, ADR 0068 AG-D7).

Every write asks for approval — that follows from its effect, never from a judgement. How the
card asks is friction: a standard card; a card with a warning that is approved on the screen
only; or a refusal Leo explains. Until `decisions` calibrates `action.friction`, the rule is
deterministic: a warning when the run read external text or the write cannot be undone,
otherwise a standard card. A judge bound later may only add friction, never remove it.
"""

from enum import IntEnum, StrEnum

from shosai.core.agent_tools.context import Taint
from shosai.core.agent_tools.spec import Reversibility


class Friction(IntEnum):
    """How a card asks, ordered from the lightest."""

    STANDARD = 0
    # Предупреждение и одобрение только на экране: не голосом, не из уведомления.
    WARNING = 1
    REFUSE = 2


def friction_rule(taint: Taint, reversibility: Reversibility) -> Friction:
    """The deterministic friction: a warning for tainted runs and irreversible writes."""
    if taint >= Taint.EXTERNAL or reversibility is Reversibility.IRREVERSIBLE:
        return Friction.WARNING
    return Friction.STANDARD


def combine(rule: Friction, judged: Friction | None) -> Friction:
    """The card's friction: the judge's answer only when it asks for more than the rule."""
    return rule if judged is None else max(rule, judged)


def screen_only(friction: Friction) -> bool:
    """Whether the card may be approved on the screen only."""
    return friction >= Friction.WARNING


class CardEnd(StrEnum):
    """How a card ended for the person: what a friction judge measures itself against."""

    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"

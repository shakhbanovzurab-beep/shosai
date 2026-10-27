"""`action.friction@1`: whether a card the rule left standard should warn (DL-D4, ADR 0069).

Every write asks for approval; friction is how the card asks. The agent's rule warns when the
run read someone else's text or the write cannot be undone; this policy is asked only when
the rule said standard, and may only turn the card into a warning — never back, never a
refusal. It asks whether the action is what the person asked for in this turn, on the items
they meant, and how far its change reaches. An unsure answer warns.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from enum import IntEnum
from typing import Final

from shosai.core.agent_tools.spec import Reversibility
from shosai.core.ai.decisions import NoulQuestion, Question, ScoreQuestion
from shosai.features.decisions.domain.calibration import Aims, CutAim
from shosai.features.decisions.domain.policy import Policy, question_text
from shosai.features.decisions.domain.state import Fact, TextField, build_state
from shosai.features.decisions.domain.verdicts import Signal, Verdict

MATCHES: Final = "matches_request"
REACH: Final = "reach"
# С какого уровня охвата изменение считается широким (0 — самый узкий).
WIDE_FROM: Final = 2
REQUEST_TOKENS: Final = 600
CARD_TOKENS: Final = 500

MATCHES_QUESTION: Final = NoulQuestion(
    instructions=(
        "Decide whether the proposed action carries out what the user asked for in their "
        "latest message, on the items they meant."
    ),
    when_true=(
        "The action is what the user asked for, applied to the items the user named or "
        "clearly meant."
    ),
    when_false=(
        "The action does something the user did not ask for, goes further than they asked, "
        "or applies to other items."
    ),
)
REACH_QUESTION: Final = ScoreQuestion(
    instructions="Rate how far the change the proposed action makes reaches.",
    criteria=(
        "Only one of the user's own items or a draft, easy to undo.",
        "Several of the user's own items.",
        "Many items, or items other people can see.",
        "Items that belong to other people, or data that cannot be restored.",
    ),
)


class CardFriction(IntEnum):
    """How a card asks, from the lightest; a higher value is more careful."""

    STANDARD = 0
    WARNING = 1


@dataclass(frozen=True, slots=True)
class CardFacts:
    """A proposed write as the card shows it, and the turn that asked for it."""

    tool: str
    toolset: str
    reversibility: Reversibility
    items: int
    # Запись в другое пространство, чем у треда (Leo §11.2).
    other_space: bool
    rounds: int
    # Вопрос человека в этом ходе и карточка словами, как он её видит.
    request: str
    card: str


class ActionFriction(Policy[CardFacts, CardFriction]):
    """Version 1: warn when the action may not be what was asked, or reaches wide."""

    point = "action.friction"
    version = 1
    deadline = timedelta(milliseconds=400)
    cuts = ("matches", "wide")
    # «Совпадает» и «узко» облегчают карточку: их точность и подгоняется; «не уверен» —
    # к осторожной стороне (не совпадает, широко).
    aims = Aims(
        cuts={
            "matches": CutAim(Verdict.YES, precision=0.9, unsure_joins=Verdict.NO),
            "wide": CutAim(Verdict.NO, precision=0.9, unsure_joins=Verdict.YES),
        },
        margin=0.05,
        accuracy_floor=0.8,
    )

    def settled(self, facts: CardFacts, rule: CardFriction) -> bool:
        """Nothing to add once the rule warns; an irreversible write always warns."""
        return rule >= CardFriction.WARNING or facts.reversibility is Reversibility.IRREVERSIBLE

    def questions(self, facts: CardFacts) -> Mapping[str, Question]:
        """Whether the action matches the request, and how far it reaches."""
        return {MATCHES: MATCHES_QUESTION, REACH: REACH_QUESTION}

    def signals(self, facts: CardFacts) -> Mapping[str, Signal]:
        """A match is read as is; reach as the chance it is wide."""
        return {MATCHES: Signal("matches"), REACH: Signal("wide", at_least=WIDE_FROM)}

    def state(self, facts: CardFacts) -> dict[str, object]:
        """The write's facts, the person's request and the card's words."""
        shown: dict[str, Fact] = {
            "tool": facts.tool,
            "reversibility": facts.reversibility.value,
            "items": facts.items,
            "other_space": facts.other_space,
        }
        texts = {
            "request": TextField(facts.request, REQUEST_TOKENS),
            "card": TextField(facts.card, CARD_TOKENS),
        }
        return build_state(shown, texts, self.budget)

    def facts(self, facts: CardFacts) -> Mapping[str, Fact]:
        """The tool, its reversibility, how many items, another space, the round."""
        return {
            "tool": facts.tool,
            "toolset": facts.toolset,
            "reversibility": facts.reversibility.value,
            "items": facts.items,
            "other_space": facts.other_space,
            "rounds": facts.rounds,
        }

    def outcome(
        self, facts: CardFacts, verdicts: Mapping[str, Verdict], chances: Mapping[str, float]
    ) -> CardFriction:
        """Standard only when the action surely matches and surely stays narrow."""
        matches = verdicts.get(MATCHES, Verdict.UNSURE) is Verdict.YES
        narrow = verdicts.get(REACH, Verdict.UNSURE) is Verdict.NO
        return CardFriction.STANDARD if matches and narrow else CardFriction.WARNING

    def careful(self, rule: CardFriction, judged: CardFriction) -> CardFriction:
        """The stronger of the two."""
        return max(rule, judged)

    def less_careful(self, value: CardFriction, rule: CardFriction) -> bool:
        """A card lighter than the rule's."""
        return value < rule

    def code(self, value: CardFriction) -> str:
        """`standard` or `warning`."""
        return value.name.lower()

    def wording(self) -> Mapping[str, object]:
        """Both questions."""
        return {MATCHES: question_text(MATCHES_QUESTION), REACH: question_text(REACH_QUESTION)}


ACTION_FRICTION: Final = ActionFriction()

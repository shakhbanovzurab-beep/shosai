"""Asking the extraction model for a turn's statements (memory step 5, Leo §7.2 "Extract").

The model reads the person's latest message, and the two exchanges before it for references
only, and answers one JSON object of the shape in `extraction_prompts` (`memory_model` asks
again once for an unreadable one). A second miss gives no statements. The call is the
person's background work under their consent, outside their Leo tokens, keyed by the run: a
redelivered admission pays once.
"""

from typing import Final

from shosai.core.ai.calls import CallOrigin, ModelRoute
from shosai.features.agent.contracts.memory import TurnWords
from shosai.features.memory.domain.admission import STATEMENTS_PER_TURN, Statement
from shosai.features.memory.domain.facts import (
    EXTRACTED_MAX,
    FactKind,
    MemoryRuleError,
    clean_statement,
)
from shosai.features.memory.infrastructure.embeddings import Payer
from shosai.features.memory.infrastructure.extraction_prompts import (
    EARLIER,
    LATEST,
    LEO_SAID,
    PERSON_SAID,
    TURN_INSTRUCTIONS,
    TurnAnswer,
)
from shosai.features.memory.infrastructure.memory_model import ChatPort, MemoryModel, ModelCall

MAX_OUTPUT_TOKENS: Final = 600


def turn_data(words: TurnWords) -> str:
    """What the model reads of a turn: the earlier exchanges, then the latest message."""
    parts: list[str] = []
    if words.before:
        parts.append(EARLIER)
        for exchange in words.before:
            parts += [PERSON_SAID.format(text=exchange.question)]
            if exchange.answer_head:
                parts += [LEO_SAID.format(text=exchange.answer_head)]
    parts += [LATEST, words.text]
    return "\n".join(parts)


def statements_of(answer: TurnAnswer) -> list[Statement]:
    """The answer's statements that keep the rules, at most three."""
    found: list[Statement] = []
    for item in answer.statements[:STATEMENTS_PER_TURN]:
        try:
            text = clean_statement(item.statement, EXTRACTED_MAX)
        except MemoryRuleError:
            continue
        found.append(
            Statement(text, FactKind(item.kind), item.explicit, item.sensitive, item.about_person)
        )
    return found


class Extractor:
    """The extraction model behind the AI port."""

    def __init__(self, ai: ChatPort, route: ModelRoute) -> None:
        self._model = MemoryModel(ai, route)

    async def turn(self, payer: Payer, words: TurnWords, key: str) -> list[Statement]:
        """The turn's statements; none when the model answers nothing readable twice."""
        call = ModelCall(
            "memory.extract", f"memory.extract:{key}", CallOrigin.BACKGROUND, MAX_OUTPUT_TOKENS
        )
        answer = await self._model.answer(
            payer, call, (TURN_INSTRUCTIONS, turn_data(words)), TurnAnswer
        )
        return [] if answer is None else statements_of(answer)

"""The summary's writer and the "Ask or update" box on memory's model (memory step 7).

The writer reads the facts and the language to write in — the interface language's own name
with its code, a value and not an instruction — and answers `SummaryAnswer`; the box reads the
facts and the person's message and answers `BoxAnswer`. A message is the person's interactive
call; a summary is their background work unless they asked for it now.
"""

from typing import Final

from shosai.core.ai.calls import CallOrigin
from shosai.core.i18n.locales import LOCALE_BY_CODE
from shosai.features.memory.infrastructure.embeddings import Payer
from shosai.features.memory.infrastructure.memory_model import MemoryModel, ModelCall
from shosai.features.memory.infrastructure.summary_prompts import (
    BOX_INSTRUCTIONS,
    FACTS_HEADER,
    MESSAGE_HEADER,
    NO_FACTS,
    SUMMARY_INSTRUCTIONS,
    BoxAnswer,
    SummaryAnswer,
)

SUMMARY_TOKENS: Final = 2_000
BOX_TOKENS: Final = 1_500
FALLBACK_LANGUAGE: Final = "en"


def language_name(code: str) -> str:
    """The language's own name and its code, English for a code outside the platform's."""
    locale = LOCALE_BY_CODE.get(code) or LOCALE_BY_CODE[FALLBACK_LANGUAGE]
    return f"{locale.endonym} ({locale.code})"


def box_data(facts: str, message: str) -> str:
    """What the box's model reads: the facts under their header, then the message."""
    return "\n".join((FACTS_HEADER, facts or NO_FACTS, "", MESSAGE_HEADER, message))


class SummaryModel:
    """Writes the summary and reads the box's messages."""

    def __init__(self, model: MemoryModel) -> None:
        self._model = model

    async def summary(
        self, payer: Payer, facts: str, language: str, call: tuple[CallOrigin, str]
    ) -> SummaryAnswer | None:
        """The overview of the facts in the language; None when nothing readable came."""
        origin, key = call
        instructions = SUMMARY_INSTRUCTIONS.replace("<language>", language_name(language))
        return await self._model.answer(
            payer,
            ModelCall("memory.summary", f"memory.summary:{key}", origin, SUMMARY_TOKENS),
            (instructions, f"{FACTS_HEADER}\n{facts}"),
            SummaryAnswer,
        )

    async def box(self, payer: Payer, facts: str, message: str, key: str) -> BoxAnswer | None:
        """What the message asks of the facts; None when nothing readable came."""
        return await self._model.answer(
            payer,
            ModelCall("memory.box", f"memory.box:{key}", CallOrigin.INTERACTIVE, BOX_TOKENS),
            (BOX_INSTRUCTIONS, box_data(facts, message)),
            BoxAnswer,
        )

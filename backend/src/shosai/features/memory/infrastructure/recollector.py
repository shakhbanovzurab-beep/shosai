"""Asking memory's model what a meeting tells about its owner (memory step 9, MM-D5).

The model reads the meeting's summary, its key points under references such as K3 with their
quotes, and the participants' names — no address, no transcript — and answers at most five
statements in the shape of `extraction_prompts.MeetingAnswer`, each citing its evidence. A
statement whose evidence is unknown, or that is about the owner while its evidence never names
them, is dropped. The call is the owner's background work under their consent, keyed by the
meeting: a redelivered task pays once.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from shosai.core.ai.calls import CallOrigin, ModelRoute
from shosai.features.memory.domain.admission import STATEMENTS_PER_MEETING, Statement
from shosai.features.memory.domain.facts import (
    EXTRACTED_MAX,
    FactKind,
    MemoryRuleError,
    clean_statement,
)
from shosai.features.memory.domain.recollections import (
    KEY_POINT_MAX,
    KEY_POINTS_MAX,
    QUOTE_MAX,
    SUMMARY_EVIDENCE,
    SUMMARY_MAX,
    clipped,
    names_owner,
)
from shosai.features.memory.infrastructure.embeddings import Payer
from shosai.features.memory.infrastructure.extraction_prompts import (
    MEETING_INSTRUCTIONS,
    MEETING_KEY_POINTS,
    MEETING_PARTICIPANTS,
    MEETING_SUMMARY,
    MeetingAnswer,
    MeetingStatement,
)
from shosai.features.memory.infrastructure.memory_model import ChatPort, MemoryModel, ModelCall

MAX_OUTPUT_TOKENS: Final = 800


@dataclass(frozen=True, slots=True)
class KeyPoint:
    """A key point of the meeting, the finding it is, and the words it rests on."""

    finding_id: UUID
    text: str
    quote: str


@dataclass(frozen=True, slots=True)
class MeetingRead:
    """What the recollection reads of a meeting, as its owner."""

    owner_name: str
    summary: str
    key_points: Sequence[KeyPoint]
    participants: Sequence[str]


@dataclass(frozen=True, slots=True)
class Recollected:
    """A statement and the references of its evidence."""

    statement: Statement
    refs: Mapping[str, str]


def meeting_data(read: MeetingRead) -> tuple[str, dict[str, KeyPoint]]:
    """What the model reads, and the key points by their references."""
    points = {f"K{index}": point for index, point in enumerate(read.key_points[:KEY_POINTS_MAX], 1)}
    lines = [MEETING_SUMMARY, clipped(read.summary, SUMMARY_MAX), "", MEETING_KEY_POINTS]
    for ref, point in points.items():
        quote = clipped(point.quote, QUOTE_MAX)
        said = f' "{quote}"' if quote else ""
        lines.append(f"{ref} {clipped(point.text, KEY_POINT_MAX)}{said}")
    lines += ["", MEETING_PARTICIPANTS, ", ".join(read.participants)]
    return "\n".join(lines), points


def evidence_of(
    item: MeetingStatement, read: MeetingRead, points: Mapping[str, KeyPoint]
) -> tuple[str, Mapping[str, str]] | None:
    """The text a statement rests on and its references; None for evidence never given."""
    if item.evidence == SUMMARY_EVIDENCE:
        return read.summary, {"evidence": SUMMARY_EVIDENCE}
    point = points.get(item.evidence)
    if point is None:
        return None
    return f"{point.text} {point.quote}", {"finding_id": str(point.finding_id)}


def recollected(
    answer: MeetingAnswer, read: MeetingRead, points: Mapping[str, KeyPoint]
) -> list[Recollected]:
    """The statements that keep the rules, at most five."""
    found: list[Recollected] = []
    for item in answer.statements[:STATEMENTS_PER_MEETING]:
        evidence = evidence_of(item, read, points)
        if evidence is None:
            continue
        text, refs = evidence
        if item.about_person and not names_owner(read.owner_name, text):
            continue
        try:
            statement = clean_statement(item.statement, EXTRACTED_MAX)
        except MemoryRuleError:
            continue
        said = Statement(
            text=statement, kind=FactKind(item.kind), explicit=False,
            sensitive=item.sensitive, about_person=item.about_person,
        )  # fmt: skip
        found.append(Recollected(said, refs))
    return found


class Recollector:
    """The recollections model behind the AI port."""

    def __init__(self, ai: ChatPort, route: ModelRoute) -> None:
        self._model = MemoryModel(ai, route)

    async def meeting(self, payer: Payer, read: MeetingRead, key: str) -> list[Recollected]:
        """The meeting's statements; none when the model answers nothing readable twice."""
        data, points = meeting_data(read)
        instructions = MEETING_INSTRUCTIONS.replace("<owner>", read.owner_name)
        call = ModelCall(
            "memory.recollect", f"memory.recollect:{key}", CallOrigin.BACKGROUND, MAX_OUTPUT_TOKENS
        )
        answer = await self._model.answer(payer, call, (instructions, data), MeetingAnswer)
        return [] if answer is None else recollected(answer, read, points)

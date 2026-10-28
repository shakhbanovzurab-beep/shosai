"""How much a run may read and how long it may go on (Leo §7.3, §8.3; ADR 0031).

The model's input is split into eight segments with hard caps, ordered from the most static
to the most volatile so the provider's prefix cache covers as much as possible; time and the
surface go last. A round may call at most eight tools; after the fourth round the model is
asked to conclude, and the tenth has no tools. A tool result over its budget enters the
context as a digest; the rest is paged with `read_result`. Token counts here are estimates
for budgeting — the provider reports the real ones — and never depend on the text's language.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

SOFT_ROUNDS: Final = 4
HARD_ROUNDS: Final = 10
CALLS_PER_ROUND: Final = 8
# Доля сегмента недавних сообщений, после которой фон сворачивает старые ходы в сводку.
COMPACTION_SHARE: Final = 0.7
# Байт UTF-8 на токен: латиница ≈ 3–4 символа на токен, кириллица ≈ 2, CJK ≈ 1 — с запасом.
BYTES_PER_TOKEN: Final = 3


class Segment(StrEnum):
    """A part of the model's input, from the most static to the most volatile."""

    POLICY = "policy"
    TOOLS = "tools"
    SKILL = "skill"
    PROFILE = "profile"
    SUMMARY = "summary"
    RECENT = "recent"
    VOLATILE = "volatile"
    QUESTION = "question"


# Политика со слоем платформы и профиль с личным контекстом — по ST-D7 (ADR 0074).
SEGMENT_CAPS: Final[dict[Segment, int]] = {
    Segment.POLICY: 2_500,
    Segment.TOOLS: 4_000,
    Segment.SKILL: 1_500,
    Segment.PROFILE: 3_200,
    Segment.SUMMARY: 1_000,
    Segment.RECENT: 5_000,
    Segment.VOLATILE: 2_500,
    Segment.QUESTION: 4_000,
}
# Граница кэша провайдера проходит после профиля: сегменты до неё стабильны между ходами.
CACHED_SEGMENTS: Final = (Segment.POLICY, Segment.TOOLS, Segment.SKILL, Segment.PROFILE)


def estimate_tokens(text: str) -> int:
    """A conservative token count of a text in any language: its UTF-8 bytes over three."""
    return math.ceil(len(text.encode()) / BYTES_PER_TOKEN)


@dataclass(frozen=True, slots=True)
class RoundPolicy:
    """What the model may do in a round."""

    tools: bool
    # Попросить модель закончить: раунды сверх мягкого предела.
    conclude: bool


def round_policy(round_number: int) -> RoundPolicy:
    """Rounds count from 1: from the fifth Leo is asked to conclude; the tenth has no tools."""
    if round_number < 1:
        message = "раунды считаются с первого"
        raise ValueError(message)
    return RoundPolicy(tools=round_number < HARD_ROUNDS, conclude=round_number > SOFT_ROUNDS)


def recent_window(newest_first: Sequence[int], cap: int = SEGMENT_CAPS[Segment.RECENT]) -> int:
    """How many of the newest messages fit the cap, given their token counts newest first.

    The thread's history is cut by tokens, never by a count of messages; a message that does
    not fit ends the window, so the window is always the newest contiguous run.
    """
    used = 0
    for taken, tokens in enumerate(newest_first):
        if used + tokens > cap:
            return taken
        used += tokens
    return len(newest_first)


def needs_compaction(recent_tokens: int, cap: int = SEGMENT_CAPS[Segment.RECENT]) -> bool:
    """Whether the recent messages passed 70% of their cap, so the summary should fold them."""
    return recent_tokens > cap * COMPACTION_SHARE


def over_budget(tokens: int, budget: int) -> bool:
    """Whether a tool's result enters the context as a digest rather than whole."""
    return tokens > budget

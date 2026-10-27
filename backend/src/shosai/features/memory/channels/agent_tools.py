"""Leo's `memory` toolset: what Leo remembers about the person, read and forgotten (step 6).

`memory.recall` reads the person's current facts in Personal and the workspaces they are in
now — the nearest to the model's query, or without one the pinned first and then the most
recently confirmed — each with its id, source and day, for "what do you know about me", "why
do you think…" and to find what to forget. A meeting's fact is the meeting's speech, so the
spec is labelled `meeting:speech` and a result with no meeting's fact narrows it to `memory`;
the result is wrapped whole, so it marks the run external even when every fact was confirmed —
stricter than MM-D7, never looser, while the turn's own recall applies MM-D7 fact by fact.
`memory.forget` ends 1 to 10 facts on one card that shows each statement as the server reads
it; a forgotten fact can be restored for 24 hours, so the write is compensable. Both are
offered only while the person's memory is on, and never over MCP (memory plan §3.2).
"""

from datetime import date, datetime, timedelta
from typing import Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from shosai.core.agent_tools.provenance import Provenance
from shosai.core.agent_tools.spec import Reversibility, ToolEffect, ToolSpec
from shosai.features.agent.contracts.memory import MEMORY_SWITCH
from shosai.features.memory.channels import agent_previews as words
from shosai.features.memory.domain.facts import STATEMENT_MAX, FactKind, MemorySource

TOOLSET: Final = "memory"
# Клиентский домен запросов кабинета, который перечитывается после записи.
MEMORY_DOMAIN: Final = ("memory",)
FOUND_MAX: Final = 20
FORGET_MAX: Final = 10


class Strict(BaseModel):
    """Tool arguments: a field the schema lacks is refused."""

    model_config = ConfigDict(extra="forbid")


class RecallMemory(Strict):
    """Arguments of reading what Leo remembers."""

    query: str | None = Field(
        default=None, min_length=1, max_length=STATEMENT_MAX,
        description=(
            "What to look for in what Leo remembers about the user. Omit it to list what Leo"
            " remembers: pinned facts first, then the most recently confirmed."
        ),
    )  # fmt: skip


class RememberedFact(BaseModel):
    """One thing Leo remembers about the user."""

    fact_id: UUID = Field(description="The fact's id, for memory.forget.")
    statement: str = Field(description="What Leo remembers, as stored.")
    kind: FactKind = Field(
        description="preference, fact, relationship, goal or procedure: what it is about."
    )
    source: MemorySource = Field(
        description=(
            "Where it came from: user_statement — the user said it in a conversation with Leo;"
            " meeting — a meeting the user was in; team_chat — a team chat; settings or"
            " user_edit — the user wrote or corrected it; imported — carried over from the"
            " user's earlier account."
        )
    )
    meeting: str | None = Field(
        description="The meeting's title, for a fact from a meeting the user can still read."
    )
    confirmed: bool = Field(
        description=(
            "Whether the user confirmed it; a fact they did not confirm was saved for them and"
            " may be wrong."
        )
    )
    pinned: bool = Field(description="Whether the user pinned it, so Leo always keeps it in mind.")
    noted_on: date = Field(description="The day it was first noted.")


class RememberedFacts(BaseModel):
    """What Leo remembers that matches."""

    facts: list[RememberedFact] = Field(
        description="Up to 20 facts, the closest to the query first; empty when nothing matches."
    )


class ForgetMemory(Strict):
    """Arguments of forgetting what Leo remembers."""

    fact_ids: list[UUID] = Field(
        min_length=1, max_length=FORGET_MAX,
        description="The ids memory.recall gave of the facts to forget, 1 to 10.",
    )  # fmt: skip


class MemoryForgotten(BaseModel):
    """What was forgotten."""

    fact_ids: list[UUID] = Field(
        description="The facts forgotten now; one forgotten or changed meanwhile is left out."
    )
    restorable_until: datetime = Field(description="Until when they can still be restored.")


RECALL: Final = ToolSpec(
    name="memory.recall", toolset=TOOLSET,
    description=(
        "Read what Leo remembers about the user: facts and preferences from their personal"
        " space and the workspaces they are in now, each with its id, source and day. With a"
        " query, the facts closest to it; without one, pinned facts first, then the most"
        " recently confirmed. Use it when the user asks what you know about them or why you"
        " think something, and to find the facts to forget."
    ),
    input=RecallMemory, output=RememberedFacts, effect=ToolEffect.READ, switch=MEMORY_SWITCH,
    result_budget=4_000, timeout=timedelta(seconds=5), provenance=Provenance.MEETING_SPEECH,
    step_detail="query",
)  # fmt: skip
FORGET: Final = ToolSpec(
    name="memory.forget", toolset=TOOLSET,
    description=(
        "Forget 1 to 10 facts Leo remembers about the user, by the ids memory.recall gave. The"
        " user approves a card showing each statement first; forgotten facts can be restored"
        " for 24 hours."
    ),
    input=ForgetMemory, output=MemoryForgotten, effect=ToolEffect.WRITE,
    reversibility=Reversibility.COMPENSABLE, switch=MEMORY_SWITCH, result_budget=600,
    timeout=timedelta(seconds=10), invalidates=MEMORY_DOMAIN, previews=(words.FORGET,),
)  # fmt: skip
MEMORY_TOOLS: Final = (RECALL, FORGET)

"""What a run did besides its answer's text: its rounds, steps, sources and taint (step 6).

The engine keeps it while the run goes on, so a run stopped or failed midway still records the
steps the person saw, the rounds the model saw and the sources it numbered. A round is the
model's message — the text it wrote before calling tools and the calls — and each call's answer
as the model read it. The run's taint only grows (Leo §7.4); its wrapper boundary is random per
run.
"""

import asyncio
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Final
from uuid import UUID

from pydantic import JsonValue

from shosai.core.agent_tools.context import Taint
from shosai.core.ai.requests import ToolCall
from shosai.core.ai.results import Usage
from shosai.features.agent.application.tool_offer import TurnOffer
from shosai.features.agent.domain.sources import SourceLedger
from shosai.features.agent.domain.wrapper import BOUNDARY_BYTES, boundary
from shosai.features.agent.infrastructure.turn_graph import ModelAnswer

DETAIL_MAX: Final = 80


@dataclass(frozen=True, slots=True)
class CallAnswer:
    """What the model read back for one call, and the stored whole result, if kept."""

    call_id: str
    # Имя инструмента из спецификации; для выдуманного моделью — имя, как она его написала.
    tool: str
    content: str
    result_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class Round:
    """One model message with tool calls, and the answers to them."""

    at: datetime
    text: str
    calls: tuple[ToolCall, ...]
    answers: tuple[CallAnswer, ...]


@dataclass(frozen=True, slots=True)
class Step:
    """A call as the person saw it: its activity, its detail, how it ended and how long."""

    seq: int
    activity: str
    detail: str | None
    status: str
    duration_ms: int
    code: str | None = None

    @property
    def id(self) -> str:
        """The step's id in the run's stream."""
        return f"step-{self.seq}"

    def stored(self) -> dict[str, JsonValue]:
        """The step as the answer's row keeps it and the history lists it."""
        return {
            "id": self.id, "activity": self.activity, "detail": self.detail,
            "status": self.status, "duration_ms": self.duration_ms, "code": self.code,
        }  # fmt: skip


def summed(usages: list[Usage | None]) -> Usage | None:
    """The usage of several calls; None when none reported any."""
    present = [usage for usage in usages if usage is not None]
    if not present:
        return None
    costs = [usage.reported_cost_usd for usage in present if usage.reported_cost_usd is not None]
    return Usage(
        input_tokens=sum(usage.input_tokens for usage in present),
        cached_tokens=sum(usage.cached_tokens for usage in present),
        output_tokens=sum(usage.output_tokens for usage in present),
        reported_cost_usd=sum(costs, Decimal(0)) if costs else None,
    )


@dataclass
class RunWork:
    """The run's rounds and steps so far, its offer of tools and its taint."""

    token: str = field(default_factory=lambda: boundary(secrets.token_bytes(BOUNDARY_BYTES)))
    offer: TurnOffer | None = None
    taint: Taint = Taint.NONE
    answers: list[ModelAnswer] = field(default_factory=list)
    rounds: list[Round] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    sources: SourceLedger = field(default_factory=SourceLedger)
    # Пространства человека с именами: читаются при первом источнике, один раз за ход.
    spaces: dict[UUID, str] | None = None
    spaces_read: asyncio.Lock = field(default_factory=asyncio.Lock)
    opened: int = field(default=0, init=False)

    def open_step(self) -> int:
        """The next step's number."""
        self.opened += 1
        return self.opened

    @property
    def tool_calls(self) -> int:
        """How many tools the model called."""
        return sum(len(each.calls) for each in self.rounds)

    def total(self, text: str) -> ModelAnswer | None:
        """The model's whole answer: all its text, the last call's end, every call's usage."""
        if not self.answers:
            return None
        last = self.answers[-1]
        return ModelAnswer(
            text=text,
            finish_reason=last.finish_reason,
            usage=summed([answer.usage for answer in self.answers]),
            first_token_ms=next(
                (a.first_token_ms for a in self.answers if a.first_token_ms is not None), None
            ),
            model=last.model,
        )

    def ordered_steps(self) -> list[dict[str, JsonValue]]:
        """The steps in the order they opened."""
        return [step.stored() for step in sorted(self.steps, key=lambda step: step.seq)]

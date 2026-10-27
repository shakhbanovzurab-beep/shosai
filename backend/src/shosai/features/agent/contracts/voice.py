"""What `capture` may use of the agent for Leo's voice mode (ADR 0070, LV-D5, LV-D6).

A voice conversation is opened on the person's thread of a space — Personal or a workspace,
a new thread when none is named. The agent gives the voice model its instruction, the answer
language and the tools of a text turn in that space and on that page: reads, and writes that
become cards for the screen. Each tool call the voice model makes runs through the agent as a
text turn's would, under the same access policy, and tells `capture` its steps and cards. Each
exchange — the person's phrase and Leo's answer, from the session's transcripts — is written
to the thread as a question and an answer with a run of channel `voice`, the run's sources and
cards with them; a completed exchange is told through the outbox like a text turn.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Final, Protocol
from uuid import UUID

from shosai.core.ai.requests import ToolSchema
from shosai.core.ports.keys import PortKey
from shosai.features.identity.contracts import Principal


@dataclass(frozen=True, slots=True)
class VoiceStart:
    """Where a voice conversation happens: the workspace or Personal, the thread, the page."""

    workspace_id: UUID | None
    thread_id: UUID | None
    path: str | None
    # Язык интерфейса: ответ — на нём, если Settings › Leo не задали другой.
    locale: str | None


@dataclass(frozen=True, slots=True)
class VoiceExchange:
    """One exchange of a conversation: what the person said and what Leo answered."""

    question: str
    answer: str
    started_at: datetime
    ended_at: datetime
    # Человек перебил Leo: ответ записан как остановленный.
    interrupted: bool = False


class VoiceEvents(Protocol):
    """What a tool call tells the conversation's socket while it runs."""

    async def step(self, activity: str, status: str) -> None:
        """A step of the call: `running`, then `done` or `failed`."""
        ...

    async def proposed(self, action_id: UUID) -> None:
        """A write became a card the person decides on the screen."""
        ...


class VoiceConversation(Protocol):
    """An open conversation: its thread, what the voice model is told, and its exchanges."""

    @property
    def thread_id(self) -> UUID:
        """The thread the exchanges go to."""
        ...

    @property
    def cross_border_consent(self) -> bool:
        """Whether the person consented to cross-border transfer: the voice call carries it."""
        ...

    @property
    def instruction(self) -> str:
        """The voice model's instruction: English, with the answer language stated."""
        ...

    @property
    def tools(self) -> tuple[ToolSchema, ...]:
        """The tools offered to the voice model, by their wire names."""
        ...

    async def call(self, call_id: str, name: str, arguments: str, events: VoiceEvents) -> str:
        """The tool's answer for the model, a JSON object; a refusal is an answer too."""
        ...

    async def record(self, exchange: VoiceExchange) -> None:
        """Write the exchange to the thread; an empty one is skipped."""
        ...


class VoiceTurns(Protocol):
    """Opens voice conversations on the agent's threads."""

    async def open(self, principal: Principal, start: VoiceStart) -> VoiceConversation:
        """A conversation; refused with `AppError` when voice mode is off for the person
        (403 `voice_mode_off`), a cross-border consent is missing (403 `consent_required`) or
        the thread is not theirs (404 `thread_not_found`)."""
        ...


VOICE_TURNS: Final = PortKey[VoiceTurns]("agent.voice_turns")

"""What other slices may use of agent, and what agent asks of them (agent plan §3.2).

`ActionProposals` puts a slice's planned write into a person's thread as an approval card
without a model round (AG-R2): chats makes tasks from a digest's items this way. The other
ports are agent's needs, bound by the slices that answer them: `decisions` judges routing
and friction (`TurnRouter`, `FrictionJudge`; until then agent's own rules decide, ADR 0068
AG-D7), `memory` recalls facts and the profile core (`MemoryRecall`, `ProfileFacts`), and
agent itself offers studio the person's installed skills (`SkillReader`). An unbound port
is read as absent (`PortDirectory.all`), never as a failure. Events are in
`contracts.events`.
"""

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from typing import Final, Protocol
from uuid import UUID

from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.context import Taint
from shosai.core.agent_tools.spec import Reversibility
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.keys import PortKey
from shosai.features.agent.domain.actions import ProposalOrigin, PublicStatus
from shosai.features.agent.domain.friction import CardEnd, Friction

__all__ = [
    "ACTION_PROPOSALS",
    "FRICTION_JUDGE",
    "MEMORY_RECALL",
    "PROFILE_FACTS",
    "SKILL_READER",
    "TURN_ROUTER",
    "ActionProposals",
    "CardEnd",
    "Friction",
    "FrictionFacts",
    "FrictionJudge",
    "InstalledSkill",
    "MemoryRecall",
    "ProfileFacts",
    "ProposalCard",
    "ProposalOrigin",
    "ProposalRefusedError",
    "ProposalRequest",
    "PublicStatus",
    "RecalledFact",
    "RouteRequest",
    "SkillReader",
    "TurnRouter",
]

ORIGIN_KEY_MAX: Final = 120


@dataclass(frozen=True, slots=True)
class ProposalRequest:
    """A write a slice plans into a person's thread, as the person (AG-R2).

    `origin_key` makes the request idempotent: the same key returns the same card.
    """

    scope: TenancyScope
    thread_id: UUID
    # Ответ, под которым встаёт карточка: тот, что показал артефакт.
    message_id: UUID
    tool: str
    arguments: Mapping[str, JsonValue]
    origin: ProposalOrigin
    origin_key: str
    language: str

    def __post_init__(self) -> None:
        if self.scope.user_id is None or not 0 < len(self.origin_key) <= ORIGIN_KEY_MAX:
            message = "предложение — от имени человека, с ключом источника до 120 символов"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class ProposalCard:
    """An action as the person's card shows it (the cabinet's `LeoProposal`)."""

    id: UUID
    tool: str
    title: str
    # «Личное» на языке человека или имя workspace, куда пишет действие.
    space: str
    origin: ProposalOrigin
    reversibility: Reversibility
    # Предупреждение: одобрять только на экране, внимательно.
    warning: bool
    # По чему готовилось действие, словами: письмо, страница; None — по словам человека.
    taint: str | None
    fields: tuple[tuple[str, str], ...]
    body: str | None
    status: PublicStatus
    outcome: str | None
    nonce: str
    created_at: datetime
    expires_at: datetime
    resolved_at: datetime | None = None


class ProposalRefusedError(AppError):
    """The slice refused to plan the write; `reason` is the tool's error code (422)."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            "proposal_refused", HTTPStatus.UNPROCESSABLE_ENTITY, params={"reason": reason}
        )


class ActionProposals(Protocol):
    """Puts a planned write into a thread as an approval card, without a model round."""

    async def propose(self, request: ProposalRequest) -> ProposalCard:
        """The stored card; the same `origin_key` again returns the same card."""
        ...


@dataclass(frozen=True, slots=True)
class RouteRequest:
    """What a router of a turn's toolsets reads: the toolsets the rule fills the room with,
    each with what its tools do (their registered English), the person's question and the
    start of the last answer, and whom the routing is for."""

    # (набор, его инструменты и первые фразы их описаний) — в порядке правила.
    candidates: tuple[tuple[str, str], ...]
    # Сколько наборов правило держит целиком и сколько токенов сегмента 2 осталось.
    forced: int
    room: int
    question: str
    previous: str
    # Раздел страницы кабинета; пусто, когда ход задан не со страницы.
    section: str
    turn: int
    language: str
    scope: TenancyScope
    cross_border_consent: bool
    run_id: UUID


class TurnRouter(Protocol):
    """Ranks the toolsets that fill a turn's room (decisions' `turn.route`); the rule keeps
    its forced part and decides alone without it. Hears which toolsets a routed run called."""

    async def route(self, request: RouteRequest) -> tuple[str, ...] | None:
        """The candidates the turn surely needs, likeliest first; None leaves the rule's order."""
        ...

    def ended(self, home: Home, run_id: UUID, called: frozenset[str]) -> None:
        """The toolsets a routed run called; never blocks, never fails."""
        ...


@dataclass(frozen=True, slots=True)
class FrictionFacts:
    """What a judge of a card's friction reads: the write, the run, the person's request and
    the card as they see it, and whom the judgement is for."""

    tool: str
    toolset: str
    reversibility: Reversibility
    taint: Taint
    # Решение правила: судья может только добавить строгости.
    rule: Friction
    # Вопрос человека в этом ходе и карточка словами — заголовок и поля, как он их видит.
    question: str
    card: str
    items: int
    # Запись в другое пространство, чем у треда (Leo §11.2).
    other_space: bool
    rounds: int
    language: str
    scope: TenancyScope
    cross_border_consent: bool
    action_id: UUID


class FrictionJudge(Protocol):
    """Judges a card's friction (decisions' `action.friction`); it may only add friction, and
    hears how each card ended so its judgements can be measured."""

    async def judge(self, facts: FrictionFacts) -> Friction | None:
        """The friction asked for, or None when the judge has nothing to add."""
        ...

    def ended(self, home: Home, action_id: UUID, end: CardEnd) -> None:
        """How a card ended — approved, rejected or expired; never blocks, never fails."""
        ...


@dataclass(frozen=True, slots=True)
class RecalledFact:
    """A fact memory recalls for a turn: the person's statement and where it came from."""

    statement: str
    kind: str
    # Метка происхождения: факт из встречи — чужая речь, оборачивается как недоверенный текст.
    source: str


class MemoryRecall(Protocol):
    """Recalls what Leo remembers about the person for a turn (memory)."""

    async def recall(
        self, home: Home, user_id: UUID, query: str, max_tokens: int
    ) -> tuple[RecalledFact, ...]:
        """The facts that matter for the query, within the budget."""
        ...


class ProfileFacts(Protocol):
    """The person's profile core for the context: pinned facts and personalization (memory)."""

    async def profile(self, home: Home, user_id: UUID, max_tokens: int) -> tuple[str, ...]:
        """Lines of the profile core, within the budget; empty when there is none."""
        ...


@dataclass(frozen=True, slots=True)
class InstalledSkill:
    """A skill the person installed, pinned to the commit it was read at."""

    id: UUID
    name: str
    description: str
    body: str
    repository: str
    path: str
    commit: str


class SkillReader(Protocol):
    """The person's installed skills, for studio's prompts (ADR 0068 AG-D11)."""

    async def skills(
        self, session: AsyncSession, user_id: UUID, ids: Collection[UUID]
    ) -> Mapping[UUID, InstalledSkill]:
        """The skills among `ids` the person installed; others are absent."""
        ...


ACTION_PROPOSALS: Final = PortKey[ActionProposals]("agent.action_proposals")
TURN_ROUTER: Final = PortKey[TurnRouter]("agent.turn_router")
FRICTION_JUDGE: Final = PortKey[FrictionJudge]("agent.friction_judge")
MEMORY_RECALL: Final = PortKey[MemoryRecall]("agent.memory_recall")
PROFILE_FACTS: Final = PortKey[ProfileFacts]("agent.profile_facts")
SKILL_READER: Final = PortKey[SkillReader]("agent.skill_reader")

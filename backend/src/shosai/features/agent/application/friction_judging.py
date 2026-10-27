"""A card's friction beyond the rule, and how each card ended (ADR 0068 AG-D7, ADR 0069 DL-D4).

The rule decides first: a warning when the run read someone else's text or the write cannot be
undone. Only a card the rule left standard goes to a bound judge (decisions' `action.friction`),
with the person's question of this turn and the card as they will read it; the card takes the
judge's friction only when it is stronger. Without a judge, or when the judge has nothing to
add, the rule's friction stands. Every card's end — approved, rejected, expired — is told to the
judges, so their judgements can be measured.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from shosai.core.agent_tools.spec import Reversibility
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.action_cards import ActionCards
from shosai.features.agent.application.run_work import RunWork
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.contracts import FRICTION_JUDGE, FrictionFacts, FrictionJudge
from shosai.features.agent.domain.action_items import ActionItem
from shosai.features.agent.domain.actions import ActionStatus
from shosai.features.agent.domain.friction import CardEnd, Friction, combine, friction_rule
from shosai.features.agent.infrastructure.thread_records import AgentMessageRecord

ENDS = {
    ActionStatus.REJECTED: CardEnd.REJECTED,
    ActionStatus.EXPIRED: CardEnd.EXPIRED,
}


class FrictionJudging:
    """Asks the bound judges for a card's friction and tells them how cards ended."""

    def __init__(
        self, ports: PortDirectory | None, cards: ActionCards, transactions: HomeTransactions
    ) -> None:
        self._ports = ports
        self._cards = cards
        self._transactions = transactions

    async def friction(
        self,
        item: ActionItem,
        org_id: UUID | None,
        run: tuple[TurnPayload, RunWork],
        action_id: UUID,
    ) -> Friction:
        """The rule's friction, raised by a judge when it asks for more."""
        payload, work = run
        rule = friction_rule(work.taint, Reversibility(item.reversibility))
        judges = self._judges()
        if rule is not Friction.STANDARD or not judges:
            return rule
        facts = FrictionFacts(
            tool=item.tool, toolset=item.tool.split(".", 1)[0],
            reversibility=Reversibility(item.reversibility), taint=work.taint, rule=rule,
            question=await self._question(payload), card=self._card(item, payload.language),
            items=len(item.targets), other_space=org_id != payload.scope().org_id,
            rounds=work.rounds_before + len(work.rounds), language=payload.language,
            scope=payload.scope(), cross_border_consent=payload.cross_border_consent,
            action_id=action_id,
        )  # fmt: skip
        friction: Friction = rule
        for judge in judges:
            friction = combine(friction, await judge.judge(facts))
        return friction

    def ended(self, home: Home, action_id: UUID, status: str, *, approved: bool = False) -> None:
        """Tell the judges how a card ended; a status that is no card's end says nothing."""
        end = CardEnd.APPROVED if approved else ENDS.get(ActionStatus(status))
        if end is None:
            return
        for judge in self._judges():
            judge.ended(home, action_id, end)

    def _judges(self) -> Sequence[FrictionJudge]:
        return () if self._ports is None else self._ports.all(FRICTION_JUDGE)

    def _card(self, item: ActionItem, language: str) -> str:
        """The card's title and fields as the person will read them."""
        rendered = self._cards.rendered(item, language)
        lines = [rendered.title, *(f"{label}: {value}" for label, value in rendered.fields)]
        if rendered.body:
            lines.append(rendered.body)
        return "\n".join(lines)

    async def _question(self, payload: TurnPayload) -> str:
        """The person's question of this turn."""
        async with self._transactions.begin(payload.scope(), read_only=True) as session:
            text = await session.scalar(
                select(AgentMessageRecord.text).where(
                    AgentMessageRecord.id == payload.question_id,
                    AgentMessageRecord.thread_id == payload.thread_id,
                )
            )
        return text or ""

"""Applying an unsubscribe link: one suppression row per (person, kind) in their home.

A valid link writes `email_suppressions` in the home it names, under the person's scope;
a repeat finds the row and changes nothing. A link that is not ours changes nothing either,
and the caller answers it exactly as a valid one, so a link reveals nobody's account.
"""

from typing import Literal

import structlog
from prometheus_client import CollectorRegistry, Counter
from sqlalchemy.dialects.postgresql import insert

from shosai.core.db.transactions import HomeTransactions
from shosai.core.email.links import UnsubscribeLinks, Unsubscription
from shosai.core.email.records import EmailSuppression
from shosai.core.kernel.tenancy import TenancyScope

type UnsubscribeOutcome = Literal["applied", "repeated", "refused"]

log = structlog.stdlib.get_logger(__name__)


class UnsubscribeMetrics:
    """`shosai_email_unsubscribes_total{source, outcome}`: links followed, by result."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._links = Counter(
            "shosai_email_unsubscribes",
            "Unsubscribe links followed, by token source and outcome.",
            ("source", "outcome"),
            registry=registry,
        )

    def counted(self, source: str, outcome: UnsubscribeOutcome) -> None:
        """One link of the source reached the outcome."""
        self._links.labels(source=source, outcome=outcome).inc()


class Unsubscribes:
    """Turns a followed link into the person's suppression."""

    def __init__(
        self,
        transactions: HomeTransactions,
        links: UnsubscribeLinks,
        metrics: UnsubscribeMetrics,
    ) -> None:
        self._transactions = transactions
        self._links = links
        self._metrics = metrics

    async def apply(self, token: str) -> UnsubscribeOutcome:
        """Suppress the kind the link names for its person, once."""
        asked = self._links.read(token)
        if asked is None:
            self._metrics.counted("unknown", "refused")
            log.info("Ссылка отписки не наша: ничего не изменено")
            return "refused"
        outcome = await self._suppressed(asked)
        source = "draft_link" if asked.from_draft else "link"
        self._metrics.counted(source, outcome)
        log.info(
            "Отписка по ссылке",
            outcome=outcome,
            source=source,
            kind=asked.kind.value,
            home=asked.home.value,
            user_id=str(asked.user_id),
        )
        return outcome

    async def _suppressed(self, asked: Unsubscription) -> UnsubscribeOutcome:
        source = "draft_link" if asked.from_draft else "link"
        async with self._transactions.begin(TenancyScope(asked.home, asked.user_id)) as session:
            written = await session.scalar(
                insert(EmailSuppression)
                .values(user_id=asked.user_id, kind=asked.kind.value, source=source)
                .on_conflict_do_nothing(
                    index_elements=[EmailSuppression.user_id, EmailSuppression.kind]
                )
                .returning(EmailSuppression.user_id)
            )
        return "applied" if written is not None else "repeated"

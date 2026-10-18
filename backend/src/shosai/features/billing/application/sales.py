"""Sales inquiries: a person asks about a custom-priced plan (the cabinet's Enterprise form).

The inquiry is stored in the person's home with `billing.sales_inquiry.received` in the
same transaction; alerting tells the owner with the ids and the team size only, and the
details stay in the home (ADR 0052).
"""

from dataclasses import dataclass
from uuid import UUID

import structlog

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.ids import new_id
from shosai.features.billing.contracts.events import SalesInquiryReceived
from shosai.features.billing.infrastructure.sales_records import SalesInquiryRecord
from shosai.features.identity.contracts import Principal

log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SalesInquiry:
    """What the person wrote to sales."""

    work_email: str
    company: str
    team_size: str
    message: str


class SalesInquiries:
    """Stores inquiries and tells the owner."""

    def __init__(self, transactions: HomeTransactions, outbox: EventOutbox) -> None:
        self._transactions = transactions
        self._outbox = outbox

    async def submit(self, principal: Principal, inquiry: SalesInquiry) -> UUID:
        """Keep the inquiry and queue the owner's notice in one transaction; its id."""
        inquiry_id = new_id()
        record = SalesInquiryRecord(
            id=inquiry_id, user_id=principal.user_id, work_email=inquiry.work_email,
            company=inquiry.company, team_size=inquiry.team_size, message=inquiry.message,
        )  # fmt: skip
        event = SalesInquiryReceived(
            inquiry_id=inquiry_id, user_id=principal.user_id, team_size=inquiry.team_size
        )
        async with self._transactions.begin(principal.scope()) as session:
            session.add(record)
            await self._outbox.add(session, event)
        log.info("Заявка в отдел продаж принята", inquiry_id=str(inquiry_id))
        return inquiry_id

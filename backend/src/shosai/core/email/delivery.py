"""The mail of one home: swept every 2 s, sent by a task, purged 7 days after (F6-C10).

The sweep claims due rows with `FOR UPDATE SKIP LOCKED`, commits, and queues one send task
per row — `critical` for account mail and notifications, `bulk` for newsletters — outside
any transaction. A send task takes the row with a 5-minute lease: a second task queued for
the same row finds the lease alive and skips it; a task that died leaves the lease to run
out, and the sweep picks the row again. The mail is rendered and handed to the SMTP server
outside any transaction, then the row is marked: sent; or queued again with a growing pause
after a transient failure, up to 8 attempts; or failed after a permanent one. Secrets are
dropped from the row once the mail reached a final state.
"""

import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Final
from uuid import UUID

import structlog
from jinja2 import TemplateError
from sqlalchemy import and_, delete, func, or_, update

from shosai.core.crypto.key_ring import FernetKeyRing
from shosai.core.db.transactions import HomeTransactions
from shosai.core.email.messages import EmailKind
from shosai.core.email.port import EmailMetrics
from shosai.core.email.records import EmailMessage
from shosai.core.email.smtp import Envelope, MailDeferredError, MailRejectedError, SmtpSender
from shosai.core.email.templates import EmailRenderer, UnknownTemplateError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.schedule.due_rows import DueRows, claim_due
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.core.tasks.payloads import HomeTaskPayload

SWEEP_LIMIT: Final = 100
SWEEP_LEASE: Final = timedelta(seconds=60)
SENDING_LEASE: Final = timedelta(minutes=5)
MAX_ATTEMPTS: Final = 8
FIRST_PAUSE: Final = timedelta(seconds=30)
LONGEST_PAUSE: Final = timedelta(hours=1)
KEEP_FINISHED: Final = timedelta(days=7)
MAIL: Final = EmailMessage.metadata.tables["email_messages"]
DUE: Final = DueRows(
    table=MAIL,
    key=MAIL.c.id,
    run_at=MAIL.c.run_at,
    pending=or_(
        MAIL.c.status == "queued",
        and_(MAIL.c.status == "sending", MAIL.c.sending_until <= func.now()),
    ),
)
log = structlog.stdlib.get_logger(__name__)


class SendEmailPayload(HomeTaskPayload):
    """The mail to send: its home and its row."""

    message_id: UUID


@dataclass(frozen=True, slots=True)
class SendTasks:
    """The send tasks by queue: account mail and notifications first, newsletters in bulk."""

    critical: TaskDeclaration[SendEmailPayload]
    bulk: TaskDeclaration[SendEmailPayload]

    def of(self, kind: str) -> TaskDeclaration[SendEmailPayload]:
        """The task of a mail's kind."""
        return self.bulk if kind == EmailKind.NEWSLETTER.value else self.critical


def pause_after(attempts: int) -> timedelta:
    """30 s after the first attempt, doubling, at most an hour."""
    return min(FIRST_PAUSE * (1 << max(attempts - 1, 0)), LONGEST_PAUSE)


class MailDelivery:
    """Sweeps, sends and purges the mail of a home."""

    def __init__(
        self,
        transactions: HomeTransactions,
        renderer: EmailRenderer,
        sender: SmtpSender,
        key_ring: FernetKeyRing | None,
        metrics: EmailMetrics,
    ) -> None:
        self._transactions = transactions
        self._renderer = renderer
        self._sender = sender
        self._key_ring = key_ring
        self._metrics = metrics

    async def claim(self, home: Home) -> list[tuple[UUID, str]]:
        """Claim the due mail of the home: (row id, kind) of each."""
        async with self._transactions.begin(TenancyScope(home)) as session:
            rows = await claim_due(session, DUE, limit=SWEEP_LIMIT, lease=SWEEP_LEASE)
        return [(row.id, row.kind) for row in rows]

    async def send(self, home: Home, message_id: UUID) -> None:
        """Send one mail if no other task holds it, and mark the outcome."""
        row = await self._taken(home, message_id)
        if row is None:
            return
        kind = EmailKind(row.kind)
        try:
            values = {**row.params, **self._opened(row.secrets)}
            rendered = self._renderer.render(
                row.template, kind, row.locale, values, row.unsubscribe_url
            )
        except (UnknownTemplateError, KeyError, TemplateError) as broken:
            log.error(
                "Письмо не собрано: шаблон или параметры",
                template=row.template,
                error_type=type(broken).__name__,
            )
            await self._finished(home, message_id, "failed", None, kind)
            return
        envelope = Envelope(row.recipient, kind, row.message_id, row.reply_to, row.unsubscribe_url)
        try:
            await self._sender.send(self._sender.message(envelope, rendered), kind)
        except MailRejectedError as rejected:
            log.warning("Сервер отказал в письме", code=rejected.code, kind=kind.value)
            await self._finished(home, message_id, "failed", rejected.code, kind)
        except MailDeferredError as deferred:
            await self._deferred(home, message_id, row.attempts, deferred.code, kind)
        else:
            await self._finished(home, message_id, "sent", 250, kind)

    async def purge(self, home: Home) -> int:
        """Delete the mail that reached a final state more than 7 days ago."""
        async with self._transactions.begin(TenancyScope(home)) as session:
            result = await session.execute(
                delete(EmailMessage).where(EmailMessage.finished_at < func.now() - KEEP_FINISHED)
            )
        return int(getattr(result, "rowcount", 0) or 0)

    async def _taken(self, home: Home, message_id: UUID) -> EmailMessage | None:
        """The row, leased for sending; None when it is sent, failed or held by another task."""
        lease = func.now() + SENDING_LEASE
        async with self._transactions.begin(TenancyScope(home)) as session:
            taken = await session.execute(
                update(EmailMessage)
                .where(EmailMessage.id == message_id, DUE.pending)
                .values(status="sending", sending_until=lease, attempts=EmailMessage.attempts + 1)
                .returning(EmailMessage)
            )
            row = taken.scalar_one_or_none()
            if row is not None:
                session.expunge(row)
        return row

    def _opened(self, sealed: bytes | None) -> dict[str, str]:
        if sealed is None or self._key_ring is None:
            return {}
        opened = json.loads(self._key_ring.decrypt(sealed))
        return {str(name): str(value) for name, value in opened.items()}

    async def _finished(
        self, home: Home, message_id: UUID, status: str, code: int | None, kind: EmailKind
    ) -> None:
        async with self._transactions.begin(TenancyScope(home)) as session:
            await session.execute(
                update(EmailMessage)
                .where(EmailMessage.id == message_id)
                .values(
                    status=status,
                    smtp_code=code,
                    finished_at=func.now(),
                    sending_until=None,
                    secrets=None,
                )
            )
        self._metrics.counted(kind, status)

    async def _deferred(
        self, home: Home, message_id: UUID, attempts: int, code: int | None, kind: EmailKind
    ) -> None:
        # attempts уже включает эту попытку: строку взяли с attempts + 1 (RETURNING).
        if attempts >= MAX_ATTEMPTS:
            log.warning("Письмо не ушло за все попытки", code=code, kind=kind.value)
            await self._finished(home, message_id, "failed", code, kind)
            return
        async with self._transactions.begin(TenancyScope(home)) as session:
            await session.execute(
                update(EmailMessage)
                .where(EmailMessage.id == message_id)
                .values(
                    status="queued",
                    smtp_code=code,
                    sending_until=None,
                    run_at=func.now() + pause_after(attempts),
                )
            )
        self._metrics.counted(kind, "deferred")
        log.info("Письмо отложено: сервер не принял его сейчас", code=code, kind=kind.value)

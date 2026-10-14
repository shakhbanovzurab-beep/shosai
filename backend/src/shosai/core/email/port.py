"""`EmailPort`: a slice puts a mail in the caller's transaction; the relay sends it (F6-C10).

`enqueue` writes the row with the effect that causes it, so a rolled-back transaction sends
nothing and a committed one is sent once by the relay. A `notification` or `newsletter` to
a person who left that kind is skipped and counted, never written; `account` mail is never
skipped. A mail of those kinds to a person carries their signed unsubscribe link
(F6-C21), naming the home of the transaction. Secret parameters are encrypted with the
Fernet key ring before they reach the row.
A campaign key already used for the recipient writes nothing: a repeated batch sends once.
"""

import json
from collections.abc import Mapping
from uuid import UUID

from prometheus_client import CollectorRegistry, Counter
from sqlalchemy import exists, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.crypto.key_ring import EncryptionKeyMissingError, FernetKeyRing
from shosai.core.db.transactions import transaction_info
from shosai.core.email.links import UnsubscribeLinks
from shosai.core.email.messages import SUPPRESSIBLE, EmailKind, OutgoingEmail
from shosai.core.email.records import EmailMessage, EmailSuppression
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id


class ReadOnlyEmailTransactionError(Exception):
    """A mail was put into a read-only transaction: it would never be committed."""


class EmailMetrics:
    """What happened to the mail: written, skipped, sent, failed, retried."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._mail = Counter(
            "shosai_email_messages",
            "Письма по виду и исходу: записано, пропущено, отправлено, не отправлено",
            ("kind", "outcome"),
            registry=registry,
        )

    def counted(self, kind: EmailKind | str, outcome: str) -> None:
        """One mail of the kind reached the outcome."""
        self._mail.labels(kind=str(kind), outcome=outcome).inc()


class EmailPort:
    """Puts mail into the caller's transaction."""

    def __init__(
        self,
        key_ring: FernetKeyRing | None,
        domains: Mapping[EmailKind, str],
        links: UnsubscribeLinks,
        metrics: EmailMetrics,
    ) -> None:
        self._key_ring = key_ring
        self._links = links
        self._domains = domains
        self._metrics = metrics

    async def enqueue(self, session: AsyncSession, email: OutgoingEmail) -> UUID | None:
        """Write the mail in the session's transaction; None when it is not to be sent."""
        info = transaction_info(session)
        if info.read_only:
            raise ReadOnlyEmailTransactionError
        if email.kind in SUPPRESSIBLE and email.user_id is not None:
            left = await session.scalar(
                select(
                    exists().where(
                        EmailSuppression.user_id == email.user_id,
                        EmailSuppression.kind == email.kind.value,
                    )
                )
            )
            if left:
                self._metrics.counted(email.kind, "suppressed")
                return None
        mail_id = new_id()
        values = {
            "id": mail_id, "user_id": email.user_id, "recipient": email.recipient,
            "locale": email.locale, "kind": email.kind.value, "template": email.template,
            "params": dict(email.params), "secrets": self._sealed(email.secrets),
            "reply_to": email.reply_to, "campaign_key": email.campaign_key,
            "unsubscribe_url": self._unsubscribe_url(info.scope.home, email),
            "message_id": f"<{mail_id.hex}@{self._domains[email.kind]}>",
        }  # fmt: skip
        written = await session.scalar(
            insert(EmailMessage)
            .values(values)
            .on_conflict_do_nothing(
                index_elements=[EmailMessage.recipient, EmailMessage.campaign_key],
                index_where=EmailMessage.campaign_key.is_not(None),
            )
            .returning(EmailMessage.id)
        )
        self._metrics.counted(email.kind, "queued" if written else "repeated")
        return written

    def _unsubscribe_url(self, home: Home, email: OutgoingEmail) -> str | None:
        if email.user_id is None:
            return None
        return self._links.url(home, email.user_id, email.kind)

    def _sealed(self, secrets: Mapping[str, str]) -> bytes | None:
        if not secrets:
            return None
        if self._key_ring is None:
            message = "FERNET_KEY не задан: письмо с секретом не записать"
            raise EncryptionKeyMissingError(message)
        return self._key_ring.encrypt(json.dumps(dict(secrets)))

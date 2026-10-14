"""Mail of a process: the port slices write with, the renderer, the SMTP sender, delivery.

The templates are installed once the slices are built: core's check mail and every slice's.
Without `FERNET_KEY` (development) the port refuses only mail that carries a secret.
"""

from dataclasses import dataclass

import structlog
from prometheus_client import CollectorRegistry

from shosai.core.config.loading import Settings
from shosai.core.crypto.key_ring import EncryptionKeyMissingError, FernetKeyRing
from shosai.core.db.transactions import HomeTransactions
from shosai.core.email.check import MAIL_CHECK
from shosai.core.email.delivery import MailDelivery
from shosai.core.email.messages import EmailKind
from shosai.core.email.port import EmailMetrics, EmailPort
from shosai.core.email.smtp import SmtpSender
from shosai.core.email.templates import EmailRenderer, EmailTemplate, EmailTemplates

log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PlatformEmail:
    """The port, the templates to install, and the delivery the mail tasks run."""

    port: EmailPort
    templates: EmailTemplates
    delivery: MailDelivery

    def install(self, templates: tuple[EmailTemplate, ...]) -> None:
        """Register core's templates and the slices'."""
        self.templates.install((MAIL_CHECK, *templates))


def key_ring_of(settings: Settings) -> FernetKeyRing | None:
    """The Fernet key ring, or None in development without a key."""
    try:
        return FernetKeyRing.from_settings(settings.crypto)
    except EncryptionKeyMissingError:
        log.warning("FERNET_KEY не задан: письма с секретами не записываются")
        return None


def renderer_of(settings: Settings, templates: EmailTemplates) -> EmailRenderer:
    """The renderer with the public address and the support mailbox."""
    email = settings.email
    return EmailRenderer(templates, str(email.public_base_url), email.support_email)


def open_email(
    settings: Settings, transactions: HomeTransactions, registry: CollectorRegistry
) -> PlatformEmail:
    """Build the mail of the process."""
    key_ring = key_ring_of(settings)
    metrics = EmailMetrics(registry)
    sender = SmtpSender(settings.email)
    templates = EmailTemplates()
    domains = {kind: sender.mailbox(kind).domain for kind in EmailKind}
    delivery = MailDelivery(
        transactions, renderer_of(settings, templates), sender, key_ring, metrics
    )
    return PlatformEmail(EmailPort(key_ring, domains, metrics), templates, delivery)

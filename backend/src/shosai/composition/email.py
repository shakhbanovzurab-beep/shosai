"""Mail of a process: the port slices write with, the renderer, the SMTP sender, delivery.

The templates are installed once the slices are built: core's check mail and every slice's.
Without `FERNET_KEY` (development) the port refuses only mail that carries a secret.
"""

from collections.abc import Mapping
from dataclasses import dataclass

import structlog
from fastapi import APIRouter
from prometheus_client import CollectorRegistry

from shosai.core.config.loading import Settings
from shosai.core.crypto.key_ring import EncryptionKeyMissingError, FernetKeyRing
from shosai.core.db.transactions import HomeTransactions
from shosai.core.email.check import MAIL_CHECK
from shosai.core.email.delivery import MailDelivery
from shosai.core.email.images import EmailImage, load_email_images
from shosai.core.email.links import UnsubscribeLinks
from shosai.core.email.messages import EmailKind
from shosai.core.email.page import UnsubscribePage
from shosai.core.email.port import EmailMetrics, EmailPort
from shosai.core.email.routes import build_email_links_router
from shosai.core.email.smtp import SmtpSender
from shosai.core.email.templates import EmailRenderer, EmailTemplate, EmailTemplates
from shosai.core.email.unsubscribe import UnsubscribeMetrics, Unsubscribes
from shosai.core.kv.rate_limits import RateLimiter

log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PlatformEmail:
    """The port, the templates to install, the delivery the mail tasks run, the link routes."""

    port: EmailPort
    templates: EmailTemplates
    delivery: MailDelivery
    unsubscribes: Unsubscribes
    images: Mapping[str, EmailImage]

    def install(self, templates: tuple[EmailTemplate, ...]) -> None:
        """Register core's templates and the slices'."""
        self.templates.install((MAIL_CHECK, *templates))

    def router(self, limiter: RateLimiter) -> APIRouter:
        """`/v1/unsubscribe` and `/email/{name}`, served by the api role."""
        return build_email_links_router(self.unsubscribes, UnsubscribePage(), self.images, limiter)


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


def links_of(settings: Settings) -> UnsubscribeLinks:
    """Unsubscribe links signed with `EMAIL_LINK_SECRET`; without it mail goes without one."""
    email = settings.email
    if email.email_link_secret is None:
        log.warning("EMAIL_LINK_SECRET не задан: письма уходят без ссылки отписки")
    return UnsubscribeLinks(
        str(email.public_base_url), email.email_link_secret, email.draft_unsubscribe_secret
    )


def open_email(
    settings: Settings, transactions: HomeTransactions, registry: CollectorRegistry
) -> PlatformEmail:
    """Build the mail of the process."""
    key_ring = key_ring_of(settings)
    links = links_of(settings)
    metrics = EmailMetrics(registry)
    sender = SmtpSender(settings.email)
    templates = EmailTemplates()
    domains = {kind: sender.mailbox(kind).domain for kind in EmailKind}
    delivery = MailDelivery(
        transactions, renderer_of(settings, templates), sender, key_ring, metrics
    )
    return PlatformEmail(
        port=EmailPort(key_ring, domains, links, metrics),
        templates=templates,
        delivery=delivery,
        unsubscribes=Unsubscribes(transactions, links, UnsubscribeMetrics(registry)),
        images=load_email_images(),
    )

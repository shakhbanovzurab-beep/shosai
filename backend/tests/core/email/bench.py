"""Mail over the run's slot and an SMTP server in the test process."""

from dataclasses import dataclass
from uuid import UUID

from cryptography.fernet import Fernet
from prometheus_client import CollectorRegistry
from pydantic import HttpUrl, SecretStr

from shosai.core.config.sections import EmailSettings, SmtpSecurity
from shosai.core.crypto.key_ring import FernetKeyRing
from shosai.core.db.transactions import HomeTransactions
from shosai.core.email.check import MAIL_CHECK
from shosai.core.email.delivery import MailDelivery
from shosai.core.email.links import UnsubscribeLinks
from shosai.core.email.messages import EmailKind
from shosai.core.email.port import EmailMetrics, EmailPort
from shosai.core.email.smtp import SmtpSender
from shosai.core.email.templates import EmailRenderer, EmailTemplate, EmailTemplates

MAIL_KEY = SecretStr(Fernet.generate_key().decode())
LINK_SECRET = SecretStr("test-link-secret-of-at-least-32-chars")
DRAFT_SECRET = SecretStr("draft-jwt-secret-for-the-test")
USER_ID = UUID("0190f0f0-0000-7000-8000-0000000000c1")
ACCOUNT_MAILBOX = "account@shosai.example"
NOTIFICATIONS_MAILBOX = "info@shosai.example"
CODE_MAIL = EmailTemplate(
    key="probe.code",
    body="{{ e.heading(t.heading) }}{{ e.code(p.code) }}"
    "{% call e.paragraph() %}{{ t.lead }}{% endcall %}",
    texts={
        "en": {"subject": "Your code {code}", "preheader": "Use it within 10 minutes.",
               "heading": "Confirm your email", "lead": "Hello, {name}."},
        "ru": {"subject": "Ваш код {code}", "preheader": "Введите его в течение 10 минут.",
               "heading": "Подтвердите почту", "lead": "Здравствуйте, {name}."},
    },
)  # fmt: skip


@dataclass
class MailBench:
    """The port, the delivery and what a test inspects."""

    port: EmailPort
    delivery: MailDelivery
    key_ring: FernetKeyRing
    registry: CollectorRegistry

    def sample(self, kind: str, outcome: str) -> float:
        """How many mails of the kind reached the outcome."""
        labels = {"kind": kind, "outcome": outcome}
        return self.registry.get_sample_value("shosai_email_messages_total", labels) or 0.0


def mail_settings(smtp_port: int) -> EmailSettings:
    """Mail to the test server, from two mailboxes without login."""
    return EmailSettings(
        smtp_host="127.0.0.1", smtp_port=smtp_port, smtp_security=SmtpSecurity.NONE,
        smtp_account_user=ACCOUNT_MAILBOX, smtp_notifications_user=NOTIFICATIONS_MAILBOX,
        smtp_account_password=None, smtp_notifications_password=None,
        public_base_url=HttpUrl("https://shosai.example"), support_email="support@shosai.example",
        email_sender_name="Shosai", email_link_secret=LINK_SECRET,
        draft_unsubscribe_secret=DRAFT_SECRET,
    )  # fmt: skip


def mail_bench(transactions: HomeTransactions, smtp_port: int) -> MailBench:
    """Mail of a process, sending to the given port."""
    registry = CollectorRegistry()
    metrics = EmailMetrics(registry)
    # Один ключ на прогон: процессы одного развёртывания делят кольцо ключей.
    key_ring = FernetKeyRing(MAIL_KEY)
    templates = EmailTemplates()
    templates.install([MAIL_CHECK, CODE_MAIL])
    settings = mail_settings(smtp_port)
    sender = SmtpSender(settings)
    renderer = EmailRenderer(templates, str(settings.public_base_url), settings.support_email)
    domains = {kind: sender.mailbox(kind).domain for kind in EmailKind}
    delivery = MailDelivery(transactions, renderer, sender, key_ring, metrics)
    port = EmailPort(key_ring, domains, mail_links(), metrics)
    return MailBench(port, delivery, key_ring, registry)


def mail_links() -> UnsubscribeLinks:
    """Links signed with the test secret, the draft's read with its test secret."""
    return UnsubscribeLinks("https://shosai.example", LINK_SECRET, DRAFT_SECRET)

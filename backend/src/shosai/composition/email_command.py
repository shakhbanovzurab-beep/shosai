"""`shosai email check --to ADDRESS [--locale LANG]`: the operator proves the mail path.

One check mail of each kind — account, notification, newsletter — is rendered in the layout
and handed to the SMTP server from its mailbox, without a queue or a database: the command
answers at once whether each mailbox delivers, and the mails show how the layout looks.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

import structlog

from shosai.composition.email import renderer_of
from shosai.composition.features import FEATURES
from shosai.composition.startup import load_process_settings
from shosai.core.config.loading import Settings
from shosai.core.config.roles import ProcessRole
from shosai.core.email.check import MAIL_CHECK
from shosai.core.email.messages import ADDRESS, EmailKind
from shosai.core.email.smtp import Envelope, MailDeferredError, MailRejectedError, SmtpSender
from shosai.core.email.templates import EmailTemplates
from shosai.core.kernel.ids import new_id
from shosai.core.observability.logs import configure_logging
from shosai.core.observability.metrics import ObservabilityMetrics, build_metrics_registry

EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
SAMPLE_CODE: Final = "123 456"
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class MailCheckCommand:
    """Where the check mail goes and in which language."""

    recipient: str
    locale: str = "en"


async def run_mail_check(environ: Mapping[str, str], command: MailCheckCommand) -> int:
    """Send the check mail of each kind; return the exit code."""
    role = ProcessRole.EMAIL
    settings = load_process_settings(environ, role, FEATURES)
    if settings is None:
        return EXIT_FAILED
    pipeline = configure_logging(
        settings.observability, role, ObservabilityMetrics(build_metrics_registry())
    )
    try:
        return await _checked(settings, command)
    finally:
        pipeline.close()


async def _checked(settings: Settings, command: MailCheckCommand) -> int:
    if not ADDRESS.fullmatch(command.recipient):
        log.error("Проверка почты не начата: адрес получателя не похож на адрес почты")
        return EXIT_FAILED
    templates = EmailTemplates()
    templates.install([MAIL_CHECK])
    renderer = renderer_of(settings, templates)
    sender = SmtpSender(settings.email)
    base_url = str(settings.email.public_base_url).rstrip("/")
    values = {"sample_code": SAMPLE_CODE, "url": f"{base_url}/app/"}
    failed = 0
    for kind in EmailKind:
        unsubscribe = None if kind is EmailKind.ACCOUNT else f"{base_url}/v1/unsubscribe"
        rendered = renderer.render(MAIL_CHECK.key, kind, command.locale, values, unsubscribe)
        message_id = f"<{new_id().hex}@{sender.mailbox(kind).domain}>"
        envelope = Envelope(command.recipient, kind, message_id, unsubscribe_url=unsubscribe)
        try:
            await sender.send(sender.message(envelope, rendered), kind)
        except (MailDeferredError, MailRejectedError) as refused:
            failed += 1
            log.error("Проверочное письмо не принято", kind=kind.value, code=refused.code)
            continue
        log.info("Проверочное письмо принято сервером", kind=kind.value,
                 mailbox=sender.mailbox(kind).address)  # fmt: skip
    return EXIT_FAILED if failed else EXIT_OK

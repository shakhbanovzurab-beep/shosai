"""Sending one mail over SMTP from the mailbox of its kind (F6-C11), and what an answer means.

One SMTP server and two mailboxes: `account` mail leaves from the account mailbox, the rest
from the notification one; `From` is the mailbox's own login, as Timeweb requires, so a
mailbox is never swapped for another address. Implicit TLS (465) or STARTTLS (587) with
certificate checks; a mailbox without a password — development, Mailpit — sends without login.

Headers (draft lessons): `Date` and a `Message-ID` on the sender's domain, which spam
filters check; the id is the row's, so a mail sent again after a crash keeps it.
`Auto-Submitted` (RFC 3834). `List-Unsubscribe` with one-click `List-Unsubscribe-Post`
(RFC 8058, required by Gmail and Yahoo) on notifications and newsletters with a link.
Header values never carry CR or LF.

A 4xx answer, a refused or dropped connection and a timeout are transient: the mail is
tried again later. A 5xx answer is permanent.
"""

from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, formatdate
from typing import Final
from urllib.parse import urlsplit

import aiosmtplib
import structlog
from pydantic import SecretStr

from shosai.core.config.sections import EmailSettings, SmtpSecurity
from shosai.core.email.messages import SUPPRESSIBLE, EmailKind
from shosai.core.email.templates import RenderedEmail

SMTP_TIMEOUT: Final = 20.0
log = structlog.stdlib.get_logger(__name__)


class MailDeferredError(Exception):
    """The server did not take the mail now; it is tried again later."""

    def __init__(self, code: int | None) -> None:
        super().__init__(code)
        self.code = code


class MailRejectedError(Exception):
    """The server refused the mail for good."""

    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class Mailbox:
    """A mailbox: its address, which is its login, and its password; none in development."""

    address: str
    user: str | None
    password: SecretStr | None

    @property
    def domain(self) -> str:
        """The domain of the address, for the Message-ID."""
        return self.address.rsplit("@", 1)[-1]


@dataclass(frozen=True, slots=True)
class Envelope:
    """What a mail carries besides its content."""

    recipient: str
    kind: EmailKind
    message_id: str
    reply_to: str | None = None
    unsubscribe_url: str | None = None


def one_line(value: str) -> str:
    """A header value without line breaks."""
    return " ".join(value.replace("\r", " ").replace("\n", " ").split())


class SmtpSender:
    """Sends mail through the configured server."""

    def __init__(self, settings: EmailSettings) -> None:
        self._settings = settings
        host = urlsplit(str(settings.public_base_url)).hostname or "localhost"
        self._mailboxes = {
            EmailKind.ACCOUNT: self._mailbox(
                settings.smtp_account_user, settings.smtp_account_password, f"account@{host}"
            ),
            EmailKind.NOTIFICATION: self._mailbox(
                settings.smtp_notifications_user,
                settings.smtp_notifications_password,
                f"notifications@{host}",
            ),
        }

    def mailbox(self, kind: EmailKind) -> Mailbox:
        """The mailbox mail of the kind leaves from."""
        return self._mailboxes[
            EmailKind.ACCOUNT if kind is EmailKind.ACCOUNT else EmailKind.NOTIFICATION
        ]

    def message(self, envelope: Envelope, rendered: RenderedEmail) -> EmailMessage:
        """The MIME message: plain text first, HTML as its alternative."""
        mailbox = self.mailbox(envelope.kind)
        message = EmailMessage()
        message["From"] = formataddr((one_line(self._settings.email_sender_name), mailbox.address))
        message["To"] = envelope.recipient
        message["Subject"] = one_line(rendered.subject)
        message["Date"] = formatdate(usegmt=True)
        message["Message-ID"] = envelope.message_id
        message["Auto-Submitted"] = "auto-generated"
        if envelope.reply_to:
            message["Reply-To"] = envelope.reply_to
        if envelope.unsubscribe_url and envelope.kind in SUPPRESSIBLE:
            message["List-Unsubscribe"] = f"<{one_line(envelope.unsubscribe_url)}>"
            message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
        message.set_content(rendered.text)
        message.add_alternative(rendered.html, subtype="html")
        return message

    async def send(self, message: EmailMessage, kind: EmailKind) -> None:
        """Hand the message to the server; `MailDeferredError` or `MailRejectedError` if not."""
        mailbox = self.mailbox(kind)
        security = self._settings.smtp_security
        # Логин только с паролем: адрес ящика без пароля — лишь отправитель (Mailpit).
        login = mailbox.user if mailbox.password else None
        try:
            await aiosmtplib.send(
                message,
                hostname=self._settings.smtp_host,
                port=self._settings.smtp_port,
                username=login,
                password=mailbox.password.get_secret_value() if mailbox.password else None,
                use_tls=security is SmtpSecurity.TLS,
                start_tls=security is SmtpSecurity.STARTTLS,
                timeout=SMTP_TIMEOUT,
            )
        except aiosmtplib.SMTPRecipientsRefused as refused:
            code = min(error.code for error in refused.recipients)
            raise _answered(code) from None
        except aiosmtplib.SMTPResponseException as answered:
            raise _answered(answered.code) from None
        except (aiosmtplib.SMTPException, OSError, TimeoutError) as failed:
            log.warning("SMTP-сервер недоступен", error_type=type(failed).__name__)
            raise MailDeferredError(None) from None

    @staticmethod
    def _mailbox(user: str | None, password: SecretStr | None, local: str) -> Mailbox:
        return Mailbox(address=user or local, user=user, password=password)


def _answered(code: int) -> MailDeferredError | MailRejectedError:
    """A server's code: 4xx is transient, 5xx permanent."""
    if 400 <= code < 500:
        return MailDeferredError(code)
    return MailRejectedError(code)

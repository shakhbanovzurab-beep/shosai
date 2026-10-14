"""An SMTP server in the test process (F6-C12): it keeps what it received and answers as told.

`CapturedEmail` runs aiosmtpd on a free loopback port. Each delivered message is kept as a
parsed `EmailMessage` with its envelope sender; the codes queued in `answers` are given to
the next messages instead of `250`, so a test plays a server that defers or refuses.
"""

from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from email import message_from_bytes, policy
from email.message import EmailMessage

from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP, Envelope, Session

from tests.core.kv.outages import closed_port


@dataclass
class CapturedEmail:
    """The messages received, with their envelope senders, and the codes still to give."""

    port: int = 0
    received: list[tuple[str, EmailMessage]] = field(default_factory=list)
    answers: deque[str] = field(default_factory=deque)

    async def handle_DATA(self, _server: SMTP, _session: Session, envelope: Envelope) -> str:  # noqa: N802
        """aiosmtpd's hook: keep the message, or give the next scripted answer."""
        if self.answers:
            return self.answers.popleft()
        parsed = message_from_bytes(envelope.original_content or b"", policy=policy.default)
        assert isinstance(parsed, EmailMessage)
        self.received.append((envelope.mail_from or "", parsed))
        return "250 Message accepted"

    @property
    def messages(self) -> list[EmailMessage]:
        """The messages received, in order."""
        return [message for _, message in self.received]


@contextmanager
def captured_email() -> Iterator[CapturedEmail]:
    """A server on a free loopback port for the block."""
    captured = CapturedEmail(port=closed_port())
    controller = Controller(captured, hostname="127.0.0.1", port=captured.port)
    controller.start()
    try:
        yield captured
    finally:
        controller.stop()

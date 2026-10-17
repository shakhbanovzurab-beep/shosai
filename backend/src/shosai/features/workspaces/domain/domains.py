"""A company's email domain: its form, the TXT record that proves it, public domains refused.

A verified domain lets people with a verified address there join the workspace with one
click (ADR 0053 point 3). A domain anyone can get an address at — a public mail service
— proves nothing about a company, so it is never accepted. The TXT record's value names
Shosai and a random token the workspace was given.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from shosai.features.workspaces.domain.public_mail_domains import PUBLIC_MAIL_DOMAINS

DOMAIN_MAX_LENGTH: Final = 253
LABEL_MAX_LENGTH: Final = 63
# Имя и зона: компания подтверждает домен второго уровня или глубже.
MIN_DOMAIN_LABELS: Final = 2
VERIFICATION_PREFIX: Final = "shosai-domain-verification="
LABEL_CHARACTERS: Final = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-")


class DomainRefusal(StrEnum):
    """Why a domain cannot be a workspace's join domain; the API's error codes."""

    INVALID = "domain_invalid"
    PUBLIC = "domain_public"


class DomainRefusedError(ValueError):
    """A domain refused, with the reason the API reports."""

    def __init__(self, refusal: DomainRefusal) -> None:
        super().__init__(refusal.value)
        self.refusal = refusal


@dataclass(frozen=True, slots=True)
class CompanyDomain:
    """A normalized domain a company may verify: lower case, ASCII (IDNA), no trailing dot."""

    value: str

    @classmethod
    def parse(cls, raw: str) -> CompanyDomain:
        """A company domain from what an admin typed; public and malformed domains refused."""
        try:
            # Как identity нормализует домен адреса: сначала нижний регистр, затем IDNA.
            ascii_form = raw.strip().rstrip(".").lower().encode("idna").decode("ascii")
        except UnicodeError as error:
            raise DomainRefusedError(DomainRefusal.INVALID) from error
        labels = ascii_form.split(".")
        if (
            len(ascii_form) > DOMAIN_MAX_LENGTH
            or len(labels) < MIN_DOMAIN_LABELS
            or not all(_label_valid(label) for label in labels)
            or labels[-1].isdigit()
        ):
            raise DomainRefusedError(DomainRefusal.INVALID)
        if ascii_form in PUBLIC_MAIL_DOMAINS:
            raise DomainRefusedError(DomainRefusal.PUBLIC)
        return cls(ascii_form)

    def verification_record(self, token: str) -> str:
        """The TXT value the company publishes at the domain to prove it is theirs."""
        return f"{VERIFICATION_PREFIX}{token}"


def _label_valid(label: str) -> bool:
    return (
        0 < len(label) <= LABEL_MAX_LENGTH
        and set(label) <= LABEL_CHARACTERS
        and not label.startswith("-")
        and not label.endswith("-")
    )

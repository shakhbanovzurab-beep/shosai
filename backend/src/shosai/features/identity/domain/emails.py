"""Email addresses as identity stores, compares and hashes them (ADR 0045).

One normalised form is the input of the directory HMAC, the uniqueness of an account in
its home and the comparison of a re-typed address before deletion. The draft lower-cased
and trimmed; v2 also encodes the domain in IDNA, so a Unicode domain and its punycode are
one address (DATA_MAPPING R4 applies the same rule to migrated accounts).
"""

from dataclasses import dataclass
from typing import Final

MIN_EMAIL_LENGTH: Final = 3
MAX_EMAIL_LENGTH: Final = 254
MAX_LOCAL_PART_LENGTH: Final = 64
# Имя и зона: адрес на голом имени хоста (user@localhost) не принимается.
MIN_DOMAIN_LABELS: Final = 2


class InvalidEmailError(ValueError):
    """The text is not an address identity accepts."""


@dataclass(frozen=True, slots=True)
class NormalizedEmail:
    """An address in identity's one normalised form."""

    value: str


def normalize_email(raw: str) -> NormalizedEmail:
    """Trim, lower-case and IDNA-encode the domain, or raise `InvalidEmailError`."""
    text = raw.strip()
    if not MIN_EMAIL_LENGTH <= len(text) <= MAX_EMAIL_LENGTH:
        message = "длина адреса вне 3–254 символов"
        raise InvalidEmailError(message)
    if any(character.isspace() for character in text):
        message = "в адресе пробельный символ"
        raise InvalidEmailError(message)
    local, separator, domain = text.partition("@")
    if not separator or not local or "@" in domain or len(local) > MAX_LOCAL_PART_LENGTH:
        message = "адрес — ровно одна @ между непустыми частями"
        raise InvalidEmailError(message)
    ascii_domain = _ascii_domain(domain)
    normalized = f"{local.lower()}@{ascii_domain}"
    if len(normalized) > MAX_EMAIL_LENGTH:
        message = "адрес длиннее 254 символов после кодирования домена"
        raise InvalidEmailError(message)
    return NormalizedEmail(normalized)


def _ascii_domain(domain: str) -> str:
    labels = domain.lower().split(".")
    if len(labels) < MIN_DOMAIN_LABELS or any(not label for label in labels):
        message = "домен адреса — хотя бы две непустые метки"
        raise InvalidEmailError(message)
    try:
        return domain.lower().encode("idna").decode("ascii")
    except UnicodeError as error:
        message = "домен адреса не кодируется в IDNA"
        raise InvalidEmailError(message) from error

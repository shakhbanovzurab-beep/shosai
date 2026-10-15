"""The one admin's credentials (ADR 0049): the hash kept in the environment and a new password.

The environment holds a bcrypt hash, never the password; a value of another form is
refused at start, so a mistyped hash does not leave the panel silently closed.
"""

import re
from typing import Final

# Хэш bcrypt: версия, стоимость 04–31, 53 знака соли и хэша.
BCRYPT_HASH: Final = re.compile(r"\$2[aby]\$(0[4-9]|[12]\d|3[01])\$[./A-Za-z0-9]{53}")
# Пароль единственного входа в админку длиннее пароля человека: его не сменить без рестарта.
MIN_ADMIN_PASSWORD_LENGTH: Final = 16
MAX_ADMIN_USERNAME_LENGTH: Final = 64


def is_bcrypt_hash(value: str) -> bool:
    """Whether the value has the form of a bcrypt hash."""
    return BCRYPT_HASH.fullmatch(value) is not None

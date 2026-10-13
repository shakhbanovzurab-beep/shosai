"""The `Idempotency-Key` header of an unsafe write (§10; api-design).

A client sends a new key for each logical operation and the same key on every retry of it.
The header is declared, so it appears in OpenAPI and a missing or malformed key is a 422
before the handler runs. The handler binds the key to its principal (`account_key`) and
passes it with the request's fingerprint to `EffectLedger.once`.
"""

from typing import Annotated, Final

from fastapi import Header

IDEMPOTENCY_KEY_HEADER: Final = "Idempotency-Key"
CLIENT_KEY_MAX_LENGTH: Final = 128

IdempotencyKeyHeader = Annotated[
    str,
    Header(
        alias=IDEMPOTENCY_KEY_HEADER,
        min_length=1,
        max_length=CLIENT_KEY_MAX_LENGTH,
        pattern=r"^[A-Za-z0-9._:-]+$",
        description=(
            "A key unique to one logical operation, repeated on each retry of it: "
            "a retry returns the first outcome and applies nothing again."
        ),
    ),
]

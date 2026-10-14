"""Unsubscribe links (F6-C21): who leaves which kind of mail, signed so nobody else can.

A v2 token names the home, the kind and the person — `v2.<home>.<kind>.<user hex>.<mac>`,
the MAC the first 128 bits of HMAC-SHA256 under `EMAIL_LINK_SECRET`, base64url — and
never expires: a person may leave a mailing from any mail they kept (38-FZ, GDPR).

A token from mail the draft sent is `<user uuid>.<first 32 hex of HMAC-SHA256>` under the
draft's JWT secret (`DRAFT_UNSUBSCRIBE_SECRET`). It stands for the draft's only opt-out,
product news, so it suppresses `newsletter` in the RU home, where every migrated account
starts (ADR 0004). Both are compared in constant time; anything else is no token.
"""

import base64
import hashlib
import hmac
from dataclasses import dataclass
from typing import Final
from urllib.parse import urlencode
from uuid import UUID

from pydantic import SecretStr

from shosai.core.email.messages import SUPPRESSIBLE, EmailKind
from shosai.core.kernel.homes import Home

V2: Final = "v2"
MAC_BYTES: Final = 16
DRAFT_MAC_HEX: Final = 32
V2_PARTS: Final = 5
# Отдельный префикс: тот же секрет не подпишет ничего, кроме ссылки отписки.
V2_DOMAIN: Final = b"shosai.email.unsubscribe.v2|"
UNSUBSCRIBE_PATH: Final = "/v1/unsubscribe"


@dataclass(frozen=True, slots=True)
class Unsubscription:
    """What a valid link asks: the person, their home and the kind they leave."""

    home: Home
    user_id: UUID
    kind: EmailKind
    from_draft: bool = False


def _v2_mac(secret: SecretStr, payload: str) -> str:
    digest = hmac.new(
        secret.get_secret_value().encode(), V2_DOMAIN + payload.encode(), hashlib.sha256
    ).digest()
    return base64.urlsafe_b64encode(digest[:MAC_BYTES]).rstrip(b"=").decode()


def _draft_mac(secret: SecretStr, raw: str) -> str:
    key = secret.get_secret_value().encode()
    return hmac.new(key, raw.encode(), hashlib.sha256).hexdigest()[:DRAFT_MAC_HEX]


def _same(expected: str, given: str) -> bool:
    """Constant-time equality; bytes, since a str with non-ASCII text cannot be compared."""
    return hmac.compare_digest(expected.encode(), given.encode("utf-8", "surrogatepass"))


class UnsubscribeLinks:
    """Signs v2 links and reads v2 and draft tokens."""

    def __init__(
        self, base_url: str, secret: SecretStr | None, draft_secret: SecretStr | None
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._secret = secret
        self._draft_secret = draft_secret

    @property
    def signing(self) -> bool:
        """Whether links can be signed; only development runs without the secret."""
        return self._secret is not None

    def url(self, home: Home, user_id: UUID, kind: EmailKind) -> str | None:
        """The link of the mail; None for a kind nobody can leave or without the secret."""
        if self._secret is None or kind not in SUPPRESSIBLE:
            return None
        payload = f"{V2}.{home.value}.{kind.value}.{user_id.hex}"
        token = f"{payload}.{_v2_mac(self._secret, payload)}"
        return f"{self._base_url}{UNSUBSCRIBE_PATH}?{urlencode({'t': token})}"

    def read(self, token: str) -> Unsubscription | None:
        """What the token asks, or None for anything not signed by us."""
        # Оба вида токенов — ASCII; иное, вплоть до одиночного суррогата, — не наш токен.
        if not token.isascii():
            return None
        if token.startswith(f"{V2}."):
            return self._read_v2(token)
        return self._read_draft(token)

    def _read_v2(self, token: str) -> Unsubscription | None:
        parts = token.split(".")
        if self._secret is None or len(parts) != V2_PARTS:
            return None
        payload, mac = token.rpartition(".")[::2]
        if not _same(_v2_mac(self._secret, payload), mac):
            return None
        # Подпись верна — значит, части записали мы сами, и разбор не упадёт.
        _, home, kind, user_hex = payload.split(".")
        return Unsubscription(Home(home), UUID(hex=user_hex), EmailKind(kind))

    def _read_draft(self, token: str) -> Unsubscription | None:
        raw, _, mac = token.partition(".")
        if self._draft_secret is None or not raw or not mac:
            return None
        if not _same(_draft_mac(self._draft_secret, raw), mac):
            return None
        try:
            user_id = UUID(raw)
        except ValueError:
            return None
        return Unsubscription(Home.RU, user_id, EmailKind.NEWSLETTER, from_draft=True)

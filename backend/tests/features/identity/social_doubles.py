"""Stand-ins for the social providers: each code or token names the identity it proves."""

from collections.abc import Mapping
from typing import Final

from shosai.features.identity.domain.social import Provider, SocialIdentity
from shosai.features.identity.infrastructure.social.base import SocialProviderFailedError

PROVIDER_PAGE: Final = "https://provider.example/authorize"
WIDGET_REDIRECT: Final = "https://shosai.example/v1/auth/social/vk/callback"


class ProviderDouble:
    """A provider that knows a fixed set of codes; anything else fails like a refusal."""

    def __init__(self, key: Provider, codes: Mapping[str, SocialIdentity]) -> None:
        self._key = key
        self._codes = codes
        self.verifiers: list[str] = []
        self.device_ids: list[str | None] = []

    @property
    def key(self) -> Provider:
        """The provider this double plays."""
        return self._key

    @property
    def widget_redirect_uri(self) -> str | None:
        """Only VK ID has a code widget (OneTap); the others answer with nothing."""
        return WIDGET_REDIRECT if self._key is Provider.VK else None

    def authorize_url(self, state: str, challenge: str) -> str:
        """A fake consent page carrying the state."""
        return f"{PROVIDER_PAGE}?provider={self._key.value}&state={state}&challenge={challenge}"

    async def identify(self, code: str, verifier: str, device_id: str | None) -> SocialIdentity:
        """The identity of a known code."""
        self.verifiers.append(verifier)
        self.device_ids.append(device_id)
        return self._known(code)

    async def identify_token(self, token: str) -> SocialIdentity:
        """The identity of a known widget token."""
        return self._known(token)

    def _known(self, code: str) -> SocialIdentity:
        if code == "explode":
            message = "сбой, которого никто не ждал"
            raise RuntimeError(message)
        identity = self._codes.get(code)
        if identity is None:
            message = "провайдер не узнал код"
            raise SocialProviderFailedError(message)
        return identity


def identity(
    provider: Provider, subject: str, email: str | None, *, verified: bool = True
) -> SocialIdentity:
    """A provider's identity of a person."""
    return SocialIdentity(provider, subject, email, verified, "Anna Petrova")

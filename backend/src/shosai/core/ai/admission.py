"""Whether a call may be sent: its provider is enabled, consent given, its model priced.

Every operation of the port is admitted here before any provider is called (F6 plan §3.3):
the model's provider has a client in this process, a Russian-home call carries the
cross-border consent (nfr-14), and the model has a price for each unit of at least one way
its kind is charged (ADR 0035: no price, no call). A refusal is counted by kind and code.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from shosai.core.ai.adapters.gemini_live import GeminiLive
from shosai.core.ai.adapters.mistral_ocr import MistralOcr
from shosai.core.ai.adapters.openai_realtime import OpenAiRealtime
from shosai.core.ai.adapters.openrouter import OpenRouter
from shosai.core.ai.calls import CallContext, ModelRef, ModelRoute, Provider
from shosai.core.ai.costs.amounts import is_priced
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.metrics import AiMetrics
from shosai.core.ai.pricing.prices import PriceBook
from shosai.core.ai.recording import MeteredCall
from shosai.core.ai.results import Unit
from shosai.core.kernel.homes import Home

TOKENS: Final = frozenset({Unit.INPUT, Unit.OUTPUT})
SECONDS: Final = frozenset({Unit.AUDIO_SECOND})
SPOKEN: Final = frozenset({Unit.INPUT_AUDIO, Unit.OUTPUT_AUDIO})
# Наборы единиц, без цены хотя бы одного из которых вызов этого вида не уходит:
# речь у одних моделей тарифицируется токенами, у других — секундами.
NEEDED_UNITS: Final = MappingProxyType(
    {
        "chat": (TOKENS,),
        "embed": (frozenset({Unit.INPUT}),),
        "rerank": (frozenset({Unit.REQUEST}),),
        # Картинка — по цене за штуку или за токены созданной картинки (прайс OpenRouter).
        "image": (frozenset({Unit.IMAGE}), frozenset({Unit.OUTPUT_IMAGE})),
        "transcribe": (TOKENS, SECONDS),
        "live_transcription": (SECONDS, TOKENS, frozenset({Unit.INPUT_AUDIO, Unit.OUTPUT})),
        "live_translation": (SECONDS, SPOKEN),
        "voice": (SPOKEN | TOKENS,),
        # Jev берёт только за входные токены: выход бесплатен (Leo §6.1).
        "decide": (frozenset({Unit.INPUT}),),
        "ocr": (frozenset({Unit.PAGE}),),
    }
)


@dataclass(frozen=True, slots=True)
class AiClients:
    """The provider clients of the process; None when the provider has no key."""

    openrouter: OpenRouter | None
    openai_realtime: OpenAiRealtime | None
    gemini_live: GeminiLive | None
    mistral: MistralOcr | None


class Admission:
    """Admits calls before they are sent and counts the refused ones."""

    def __init__(self, prices: PriceBook, metrics: AiMetrics) -> None:
        self._prices = prices
        self._metrics = metrics

    def client[C](self, client: C | None, provider: Provider, model: ModelRef, kind: str) -> C:
        """The client of the model's provider; refused when absent or of another provider."""
        if client is None or model.provider is not provider:
            raise self.refuse(kind, AiFailure.MODEL_UNAVAILABLE)
        return client

    async def admit(self, context: CallContext, route: ModelRoute, kind: str) -> MeteredCall:
        """The call that may be sent, with its prices; `AiCallError` otherwise."""
        scope = context.scope
        if scope is not None and scope.home is Home.RU and not context.cross_border_consent:
            raise self.refuse(kind, AiFailure.CONSENT_REQUIRED)
        prices = await self._prices.prices_of(route.primary)
        if not is_priced(prices, NEEDED_UNITS[kind]):
            raise self.refuse(kind, AiFailure.MODEL_UNPRICED)
        return MeteredCall(context, route.primary, kind, prices)

    def refuse(self, kind: str, failure: AiFailure) -> AiCallError:
        """The error of a refused call, counted."""
        self._metrics.refused(kind, failure.value)
        return AiCallError(failure)

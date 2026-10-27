"""Vectors of questions and statements through the provider port (MM-D6, plan §1.4).

`google/gemini-embedding-2` takes no task type: the task goes into the text, a question as a
search query and a statement as a document; both prefixes are model-facing text, registered in
the English test. Every call is the person's: it needs their cross-border consent in the
Russian home, and it is paid outside their Leo tokens. A question's call is on a turn's path,
so its cost row is written later, off the path (as decisions', ADR 0069 DL-D2).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Final, Protocol

from shosai.core.ai.calls import CallClass, CallContext, CallOrigin, ModelRoute
from shosai.core.ai.requests import EmbeddingRequest
from shosai.core.ai.results import Embeddings
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.memory.infrastructure.records import EMBEDDING_DIMENSIONS

QUERY_PREFIX: Final = "task: search result | query: "
DOCUMENT_PREFIX: Final = "title: none | text: "
EMBEDDING_TEXTS: Final[tuple[object, ...]] = (QUERY_PREFIX, DOCUMENT_PREFIX)
# Не больше стольких текстов в одном вызове: поставщик отказывает пакетам крупнее.
BATCH: Final = 50


class EmbeddingPort(Protocol):
    """The provider port's embedding call."""

    async def embed(
        self,
        context: CallContext,
        route: ModelRoute,
        request: EmbeddingRequest,
        *,
        cost_later: bool = False,
    ) -> Embeddings:
        """Vectors of texts, in order."""
        ...


@dataclass(frozen=True, slots=True)
class Payer:
    """Whose call it is and whether their text may cross the border."""

    scope: TenancyScope
    consent: bool


class Embedder:
    """Embeds a turn's question and the person's statements."""

    def __init__(self, port: EmbeddingPort, route: ModelRoute) -> None:
        self._port = port
        self._route = route

    @property
    def model(self) -> str:
        """The model whose vectors these are."""
        return self._route.primary.model

    async def question(self, payer: Payer, text: str, key: str, deadline: timedelta) -> list[float]:
        """The vector of a turn's question; its cost row is written off the turn's path."""
        context = self._context(payer, f"memory.recall:{key}", deadline)
        request = EmbeddingRequest((QUERY_PREFIX + text,), EMBEDDING_DIMENSIONS)
        answer = await self._port.embed(context, self._route, request, cost_later=True)
        return list(answer.vectors[0])

    async def statements(self, payer: Payer, texts: Sequence[str], key: str) -> list[list[float]]:
        """The vectors of statements to store, in batches the provider accepts."""
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH):
            part = tuple(DOCUMENT_PREFIX + text for text in texts[start : start + BATCH])
            context = self._context(payer, f"memory.embed:{key}:{start}", timedelta(seconds=30))
            answer = await self._port.embed(
                context, self._route, EmbeddingRequest(part, EMBEDDING_DIMENSIONS)
            )
            vectors += [list(vector) for vector in answer.vectors]
        return vectors

    @staticmethod
    def _context(payer: Payer, key: str, deadline: timedelta) -> CallContext:
        return CallContext(
            effect_key=key,
            feature="memory.embed",
            call_class=CallClass.STANDARD,
            origin=CallOrigin.BACKGROUND,
            scope=payer.scope,
            cross_border_consent=payer.consent,
            deadline=deadline,
        )

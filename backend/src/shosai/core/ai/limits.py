"""Input caps: what one call may carry, checked before any provider is called (§3.7).

A conversation may hold at most so many tokens of context (counted as the estimates count
them), so many images and images of at most so many megabytes; a decision's state and an
embedding's texts are held to the same context cap. A call over a cap is refused with
`input_too_large`, whose English text tells a model what to change.
"""

from dataclasses import dataclass
from typing import Final

from shosai.core.ai.decisions import DecisionRequest
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.requests import ChatRequest, EmbeddingRequest, ImagePart
from shosai.core.ai.spend.estimates import chat_estimate, decision_estimate, embedding_estimate

MEGABYTE: Final = 1024 * 1024


@dataclass(frozen=True, slots=True)
class InputCaps:
    """The caps from settings."""

    context_tokens: int
    images: int
    image_bytes: int

    def check_chat(self, request: ChatRequest) -> None:
        """Refuse a conversation over a cap."""
        images = [p for m in request.messages for p in m.parts if isinstance(p, ImagePart)]
        if len(images) > self.images or any(len(i.data) > self.image_bytes for i in images):
            raise AiCallError(AiFailure.INPUT_TOO_LARGE)
        self._context(chat_estimate(request).input_tokens)

    def check_embedding(self, request: EmbeddingRequest) -> None:
        """Refuse texts over the context cap."""
        self._context(embedding_estimate(request).input_tokens)

    def check_decision(self, request: DecisionRequest) -> None:
        """Refuse a decision's state over the context cap."""
        self._context(decision_estimate(request).input_tokens)

    def _context(self, tokens: int) -> None:
        if tokens > self.context_tokens:
            raise AiCallError(AiFailure.INPUT_TOO_LARGE)

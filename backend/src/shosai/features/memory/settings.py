"""The memory slice's settings (`MEMORY_*`, memory plan §3.2).

`MEMORY_MODEL` (with `MEMORY_FALLBACK_MODEL`) finds statements in a turn and a meeting, writes
the summary and reads the summary's box, until studio's model routes. `MEMORY_EMBEDDING_MODEL`
turns statements and questions into vectors: the owner's
`google/gemini-embedding-2` (MM-D6), asked for 1 024 of its Matryoshka dimensions. A change of
model re-embeds every fact on a cursor; recall never compares vectors of two models.
"""

import re
from typing import Final, Self

from pydantic import model_validator

from shosai.core.ai.calls import ModelRef, ModelRoute, Provider
from shosai.core.config.sections import SettingsSection

PINNED_MODEL: Final = re.compile(r"[a-z0-9_.-]+/[a-z0-9_.-]+")


class MemorySettings(SettingsSection):
    """Which model gives memory its vectors."""

    memory_model: str = "google/gemini-3.8-flash"
    memory_fallback_model: str | None = None
    memory_embedding_model: str = "google/gemini-embedding-2"

    @model_validator(mode="after")
    def named(self) -> Self:
        """Refuse a name that is not a provider's model: vectors belong to one model."""
        model = self.memory_embedding_model
        if not PINNED_MODEL.fullmatch(model) or model.endswith("latest"):
            message = "MEMORY_EMBEDDING_MODEL — модель поставщика, не псевдоним"
            raise ValueError(message)
        return self

    def embedding_route(self) -> ModelRoute:
        """The route of every embedding: one model, no fallback of another kind."""
        return ModelRoute(ModelRef(Provider.OPENROUTER, self.memory_embedding_model))

    def model_route(self) -> ModelRoute:
        """The route of memory's own model calls, its fallback after it when one is set."""
        fallbacks = (
            (ModelRef(Provider.OPENROUTER, self.memory_fallback_model),)
            if self.memory_fallback_model
            else ()
        )
        return ModelRoute(ModelRef(Provider.OPENROUTER, self.memory_model), fallbacks)

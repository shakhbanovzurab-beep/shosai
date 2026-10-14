"""Registry of text a language model reads (CLAUDE.md, "Prompts and model-facing text").

It covers everything a model sees: system instructions, names and descriptions of tools
and their parameters, enum values, tool results, error texts returned to a model, service
markers in a thread, MCP server instructions, prompts of auxiliary models. A slice registers
a new source in the same commit that adds it; unregistered text is not protected.

`collect` returns the objects as they are: strings, mappings and lists (tool schemas),
enums, Pydantic models (a class stands for its JSON schema, an instance for its data).
`allowed_literals` holds only legitimate non-English values such as language endonyms,
never instructions.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from shosai.core.ai.errors import MODEL_TEXTS


@dataclass(frozen=True, slots=True)
class ModelFacingSource:
    """One source of model-facing text and the slice that owns it."""

    owner: str
    name: str
    collect: Callable[[], Iterable[object]]
    allowed_literals: frozenset[str] = field(default_factory=frozenset)


def ai_failure_texts() -> Iterable[object]:
    """What a model reads when its call through the AI port failed."""
    return MODEL_TEXTS.values()


MODEL_FACING_SOURCES: tuple[ModelFacingSource, ...] = (
    ModelFacingSource(owner="core.ai", name="failure texts", collect=ai_failure_texts),
)

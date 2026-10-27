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
from functools import partial
from typing import Any

from shosai.composition.features import FEATURES
from shosai.core.agent_tools.results import TOOL_ERROR_TEXTS, ToolErrorCode
from shosai.core.agent_tools.spec import ToolSpec
from shosai.core.ai.errors import MODEL_TEXTS
from shosai.features.agent.application.surface_digest import SUBJECT_TEXTS
from shosai.features.agent.domain.context import CONTEXT_TEXTS
from shosai.features.agent.infrastructure.eval_prompts import JUDGE_TEXTS
from shosai.features.agent.infrastructure.prompts import PROMPT_TEXTS as AGENT_PROMPTS
from shosai.features.agent.infrastructure.voice_prompts import VOICE_PROMPT_TEXTS
from shosai.features.capture.infrastructure.voice_texts import VOICE_TEXTS
from shosai.features.decisions.domain.policies import policy_wording
from shosai.features.decisions.infrastructure.generation_texts import generation_texts
from shosai.features.notes.infrastructure.prompts import PROMPT_TEXTS as NOTES_PROMPTS


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


def tool_error_texts() -> Iterable[object]:
    """What a model reads when a tool call failed: the codes and their texts."""
    return [ToolErrorCode, *TOOL_ERROR_TEXTS.values()]


def tool_spec_texts(specs: Iterable[ToolSpec[Any, Any]]) -> Iterable[object]:
    """What a model reads of each tool: name, description, and both schemas with their
    field descriptions and enum values (a model class stands for its JSON schema)."""
    for spec in specs:
        yield from (spec.name, spec.description, spec.input, spec.output)


def slice_tool_sources() -> tuple[ModelFacingSource, ...]:
    """The agent tools every listed slice declares, one source per slice."""
    return tuple(
        ModelFacingSource(
            owner=feature.name,
            name="agent tools",
            collect=partial(tool_spec_texts, feature.agent_tools),
        )
        for feature in FEATURES
        if feature.agent_tools
    )


MODEL_FACING_SOURCES: tuple[ModelFacingSource, ...] = (
    ModelFacingSource(owner="core.ai", name="failure texts", collect=ai_failure_texts),
    ModelFacingSource(owner="core.agent_tools", name="error texts", collect=tool_error_texts),
    ModelFacingSource(owner="notes", name="notes prompts", collect=lambda: NOTES_PROMPTS),
    ModelFacingSource(owner="agent", name="Leo's policy", collect=lambda: AGENT_PROMPTS),
    ModelFacingSource(owner="agent", name="Leo's voice", collect=lambda: VOICE_PROMPT_TEXTS),
    ModelFacingSource(owner="capture", name="voice tool failure", collect=lambda: VOICE_TEXTS),
    ModelFacingSource(owner="agent", name="Leo's context", collect=lambda: CONTEXT_TEXTS),
    ModelFacingSource(owner="agent", name="Leo's page subjects", collect=lambda: SUBJECT_TEXTS),
    ModelFacingSource(owner="agent", name="the evaluation's judge", collect=lambda: JUDGE_TEXTS),
    ModelFacingSource(owner="decisions", name="Jev questions", collect=lambda: [policy_wording()]),
    ModelFacingSource(owner="decisions", name="dataset tools", collect=generation_texts),
    *slice_tool_sources(),
)

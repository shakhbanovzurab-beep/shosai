"""The CLAUDE.md "Prompts" gate: all registered model-facing text is English."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from shosai.core.agent_tools.spec import ToolEffect, ToolSpec
from tests.model_facing.collector import find_violations
from tests.model_facing.registry import MODEL_FACING_SOURCES, ModelFacingSource, tool_spec_texts


def test_every_registered_model_facing_text_is_english() -> None:
    assert find_violations(MODEL_FACING_SOURCES) == []


def test_every_source_is_registered_once() -> None:
    keys = [(source.owner, source.name) for source in MODEL_FACING_SOURCES]

    assert len(keys) == len(set(keys))


class ProbeMode(StrEnum):
    """An enum of a tool input; its values reach the model in the schema."""

    QUICK = "quick"
    PLANTED = "быстро"


class ProbeInput(BaseModel):
    """Arguments of a planted tool."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(description="What to look for.")
    mode: ProbeMode = ProbeMode.QUICK


class ProbeOutput(BaseModel):
    """Result of a planted tool."""

    found: int = Field(description="Сколько найдено.")


def planted_spec(description: str) -> ToolSpec[ProbeInput, ProbeOutput]:
    """A read tool with the given description."""
    return ToolSpec(
        name="probe.search",
        toolset="probe",
        description=description,
        input=ProbeInput,
        output=ProbeOutput,
        effect=ToolEffect.READ,
    )


def test_a_tool_spec_with_non_english_text_fails_the_check() -> None:
    source = ModelFacingSource(
        owner="probe",
        name="agent tools",
        collect=lambda: tool_spec_texts([planted_spec("Найти встречи по запросу.")]),
    )

    violations = find_violations([source])

    assert any("$: " in violation and "Найти" in violation for violation in violations)
    assert any("быстро" in violation for violation in violations)
    assert any("Сколько найдено" in violation for violation in violations)

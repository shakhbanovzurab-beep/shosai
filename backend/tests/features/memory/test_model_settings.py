"""Memory's model route from the settings: its models and how hard the primary reasons.

gemini-3.8-flash's default reasoning spent 573 of an extraction's 600 output tokens on a long
message and cut the answer off, so nothing was admitted (measured on staging's turns,
2026-10-27); the primary model reasons `minimal` unless the setting says otherwise, and the
fallback keeps its provider's default.
"""

from shosai.core.ai.calls import ModelRef, ModelRoute, Provider
from shosai.core.ai.requests import ReasoningEffort
from shosai.features.memory.settings import MemorySettings

PRIMARY = "google/gemini-3.8-flash"
FALLBACK = "anthropic/claude-haiku-5.5"


def test_the_primary_model_reasons_minimal_unless_the_setting_says_otherwise() -> None:
    chosen = MemorySettings.model_validate({"memory_reasoning": "low"})
    provider = MemorySettings.model_validate({"memory_reasoning": None})

    assert MemorySettings(memory_fallback_model=FALLBACK).model_route() == ModelRoute(
        ModelRef(Provider.OPENROUTER, PRIMARY),
        (ModelRef(Provider.OPENROUTER, FALLBACK),),
        reasoning=ReasoningEffort.MINIMAL,
    )
    assert [chosen.model_route().reasoning, provider.model_route().reasoning] == [
        ReasoningEffort.LOW,
        None,
    ]

"""OpenRouter's model list as studio reads it: readable entries only, one request per period."""

import asyncio

import httpx
import pytest

from shosai.core.ai.adapters.openrouter import OPENROUTER_API
from shosai.core.ai.listing import (
    ListedModel,
    ModelListUnavailableError,
    OpenRouterModels,
    listed_models,
)
from tests.doubles.openrouter import ScriptedOpenRouter

GOOD = {
    "id": "google/gemini-3.8-flash", "name": "Google: Gemini 3.8 Flash",
    "context_length": 1_048_576,
    "top_provider": {"max_completion_tokens": 65_536},
    "architecture": {"input_modalities": ["text", "image", 7], "output_modalities": ["text"]},
    "supported_parameters": ["temperature", "reasoning"],
}  # fmt: skip


def test_readable_entries_are_kept_and_the_rest_skipped() -> None:
    models = listed_models(
        {"data": [GOOD, {"id": "x/y"}, {"id": "", "context_length": 1}, "odd", {"id": 5}]}
    )

    assert dict(models) == {
        "google/gemini-3.8-flash": ListedModel(
            id="google/gemini-3.8-flash",
            name="Google: Gemini 3.8 Flash",
            context_length=1_048_576,
            max_output_tokens=65_536,
            input_modalities=frozenset({"text", "image"}),
            output_modalities=frozenset({"text"}),
            parameters=frozenset({"temperature", "reasoning"}),
        )
    }


def test_a_list_without_data_is_an_error_not_an_empty_catalogue() -> None:
    with pytest.raises(ModelListUnavailableError):
        listed_models({"error": "maintenance"})


async def test_one_request_serves_every_caller_until_it_ages_and_failures_are_explicit() -> None:
    openrouter = ScriptedOpenRouter()
    openrouter.answer("models", httpx.Response(200, json={"data": [GOOD]}))
    models = OpenRouterModels(openrouter.client(), OPENROUTER_API)
    failing = ScriptedOpenRouter()
    failing.answer("models", httpx.Response(502))

    first, second = await asyncio.gather(models.listed(), models.listed())

    assert first is second
    assert len(openrouter.requests) == 1
    with pytest.raises(ModelListUnavailableError):
        await OpenRouterModels(failing.client(), OPENROUTER_API).listed()

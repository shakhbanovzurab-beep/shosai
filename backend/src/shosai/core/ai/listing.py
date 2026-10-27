"""What providers list and charge: OpenRouter's models with their metadata, and the prices in
force (studio plan §3.2, ADR 0074).

Studio's catalogue describes the models the operator lists from OpenRouter's public model
list — name, window, output limit, what a model reads and which parameters it takes — and
proposes a tier from the price in force, which F6's daily sync records. The list is one GET,
read at most once in five minutes per process, so an operator adding several models costs
one request; an answer that cannot be read is an explicit error, never an empty list.
"""

import asyncio
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from types import MappingProxyType
from typing import Final

import httpx
import structlog

from shosai.core.ai.pricing.prices import PriceBook

LIST_DEADLINE: Final = timedelta(seconds=30)
LIST_TTL: Final = timedelta(minutes=5)
MODEL_ID_MAX: Final = 128
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ListedModel:
    """What OpenRouter's list says of one model."""

    id: str
    name: str
    context_length: int
    max_output_tokens: int | None
    input_modalities: frozenset[str]
    output_modalities: frozenset[str]
    parameters: frozenset[str]


class ModelListUnavailableError(Exception):
    """OpenRouter's model list could not be read now."""


def strings(value: object) -> frozenset[str]:
    """The strings of a JSON list; anything else is none."""
    if not isinstance(value, list):
        return frozenset()
    return frozenset(item for item in value if isinstance(item, str))


def listed_model(entry: object) -> ListedModel | None:
    """One entry of the list, or none when it cannot be read."""
    if not isinstance(entry, dict):
        return None
    model_id, name, window = entry.get("id"), entry.get("name"), entry.get("context_length")
    if not isinstance(model_id, str) or not 0 < len(model_id) <= MODEL_ID_MAX:
        return None
    if not isinstance(window, int) or isinstance(window, bool) or window < 0:
        return None
    architecture = entry.get("architecture")
    architecture = architecture if isinstance(architecture, dict) else {}
    provider = entry.get("top_provider")
    output = provider.get("max_completion_tokens") if isinstance(provider, dict) else None
    output = output if isinstance(output, int) and not isinstance(output, bool) else None
    return ListedModel(
        id=model_id,
        name=name if isinstance(name, str) else model_id,
        context_length=window,
        max_output_tokens=output if output is None or output >= 0 else None,
        input_modalities=strings(architecture.get("input_modalities")),
        output_modalities=strings(architecture.get("output_modalities")),
        parameters=strings(entry.get("supported_parameters")),
    )


def listed_models(document: object) -> Mapping[str, ListedModel]:
    """Every readable model of the list, by id."""
    rows = document.get("data") if isinstance(document, dict) else None
    if not isinstance(rows, list):
        message = "в списке моделей OpenRouter нет data"
        raise ModelListUnavailableError(message)
    found = (listed_model(entry) for entry in rows)
    return MappingProxyType({model.id: model for model in found if model is not None})


@dataclass(frozen=True, slots=True)
class _Snapshot:
    models: Mapping[str, ListedModel]
    taken_at: float


class OpenRouterModels:
    """OpenRouter's model list, read at most once in five minutes per process."""

    def __init__(self, client: httpx.AsyncClient, base_url: str, ttl: timedelta = LIST_TTL) -> None:
        self._client = client
        self._url = base_url.rstrip("/") + "/models"
        self._ttl = ttl.total_seconds()
        self._snapshot: _Snapshot | None = None
        self._lock = asyncio.Lock()

    async def listed(self) -> Mapping[str, ListedModel]:
        """Every model OpenRouter lists now; raises `ModelListUnavailableError`."""
        snapshot = self._snapshot
        if snapshot is not None and time.monotonic() - snapshot.taken_at < self._ttl:
            return snapshot.models
        # Один процесс — один запрос: остальные ждут его, а не идут к OpenRouter вслед.
        async with self._lock:
            snapshot = self._snapshot
            if snapshot is None or time.monotonic() - snapshot.taken_at >= self._ttl:
                snapshot = _Snapshot(await self._read(), time.monotonic())
                self._snapshot = snapshot
        return snapshot.models

    async def _read(self) -> Mapping[str, ListedModel]:
        try:
            response = await self._client.get(
                self._url,
                params={"output_modalities": "all"},
                timeout=LIST_DEADLINE.total_seconds(),
            )
            response.raise_for_status()
            document = response.json()
        except (httpx.HTTPError, ValueError) as error:
            log.warning("Список моделей OpenRouter не прочитан", error=type(error).__name__)
            message = "список моделей OpenRouter не прочитан"
            raise ModelListUnavailableError(message) from error
        models = listed_models(document)
        log.info("Список моделей OpenRouter прочитан", models=len(models))
        return models


@dataclass(frozen=True, slots=True)
class ModelListing:
    """OpenRouter's models with their metadata and the prices in force, for studio."""

    openrouter: OpenRouterModels
    prices: PriceBook

"""Whether OpenRouter keeps a model's prompts: its zero-data-retention list (ADR 0069 DL-D1).

Two public reads, no key needed (read on 2026-10-26):

- `GET /api/v1/endpoints/zdr` lists every endpoint with a zero-data-retention policy:
  `{data: [{model_id, provider_name, tag, …}]}`; OpenRouter updates it "when there are
  changes to a provider's data policy";
- `GET /api/v1/models/{model}/endpoints` lists every endpoint of one model:
  `{data: {id, endpoints: [{provider_name, tag, …}]}}`.

A model keeps nothing only when it has endpoints and every one of them is on the list:
an endpoint off the list is one OpenRouter may route the call to. Anything malformed is
read as "not zero retention", never as a guess.
"""

from collections.abc import Iterable
from datetime import timedelta
from typing import Final

import httpx

from shosai.core.ai.adapters.openrouter import OPENROUTER_API

FETCH_DEADLINE: Final = timedelta(seconds=30)


def listed_endpoints(document: object) -> frozenset[tuple[str, str]]:
    """The (model, tag) pairs on the zero-data-retention list."""
    rows = document.get("data") if isinstance(document, dict) else None
    pairs: set[tuple[str, str]] = set()
    for row in rows if isinstance(rows, list) else ():
        if isinstance(row, dict):
            model, tag = row.get("model_id"), row.get("tag")
            if isinstance(model, str) and isinstance(tag, str):
                pairs.add((model, tag))
    return frozenset(pairs)


def model_tags(document: object) -> tuple[str, ...] | None:
    """The tags of a model's endpoints; None when the answer is not the model's list."""
    data = document.get("data") if isinstance(document, dict) else None
    endpoints = data.get("endpoints") if isinstance(data, dict) else None
    if not isinstance(endpoints, list):
        return None
    tags = [endpoint.get("tag") for endpoint in endpoints if isinstance(endpoint, dict)]
    if len(tags) != len(endpoints) or not all(isinstance(tag, str) for tag in tags):
        return None
    return tuple(str(tag) for tag in tags)


def keeps_nothing(
    model: str, tags: Iterable[str] | None, listed: frozenset[tuple[str, str]]
) -> bool:
    """Whether the model has endpoints and every one is on the list."""
    endpoints = tuple(tags or ())
    return bool(endpoints) and all((model, tag) in listed for tag in endpoints)


async def zero_retention(
    client: httpx.AsyncClient, model: str, base_url: str = OPENROUTER_API
) -> bool:
    """Read both lists and say whether every endpoint of the model keeps nothing.

    Raises `httpx.HTTPError` when either read fails: the caller keeps the last status it had.
    """
    base = base_url.rstrip("/")
    timeout = FETCH_DEADLINE.total_seconds()
    listed = await client.get(f"{base}/endpoints/zdr", timeout=timeout)
    listed.raise_for_status()
    endpoints = await client.get(f"{base}/models/{model}/endpoints", timeout=timeout)
    endpoints.raise_for_status()
    return keeps_nothing(model, model_tags(endpoints.json()), listed_endpoints(listed.json()))

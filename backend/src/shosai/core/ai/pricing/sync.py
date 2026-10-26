"""The daily sync of OpenRouter's prices into the price list of the EU home (ADR 0035).

One GET of the public model list; a price that differs from the one in force is appended as
a new row from now, an equal one writes nothing, a model gone from the list keeps its last
price. OpenRouter's `pricing` names units by field (read on 2026-10-13):

- `prompt` and `completion` are USD per input and output token — except for a transcription
  model without a `completion` price, whose `prompt` is per second of audio (OpenAI's own
  list confirms it: gpt-transcribe $0.0045 a minute is OpenRouter's 0.000075)
- `input_cache_read` is per cached input token, `audio` and `audio_output` per audio token
- `image_token` and `image_output` are per image token, of the pictures a call is given and of
  the one it makes (read on 2026-10-26); `image`, a price per given picture, is not recorded:
  the price list's `image` unit is per picture made
- a negative price marks a router whose price varies: skipped; `overrides` for long prompts
  are not followed, the base price is the one recorded

A per-second price above $0.01 ($36 an hour) fits no speech model and is skipped as a unit
the sync cannot read; an operator prices such a model by hand.
"""

from collections.abc import Iterator, Mapping
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Final

import httpx
import structlog
from sqlalchemy import func, insert, select
from sqlalchemy.dialects.postgresql import distinct_on

from shosai.core.ai.adapters.openrouter import OPENROUTER_API
from shosai.core.ai.calls import Provider
from shosai.core.ai.pricing.records import ProviderPrice
from shosai.core.ai.results import Unit
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler, TaskKind
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue

FETCH_DEADLINE: Final = timedelta(seconds=30)
PRICE_STEP: Final = Decimal("1e-12")
MAX_PER_SECOND: Final = Decimal("0.01")
MODEL_NAME_MAX: Final = 128
FIELDS: Final = {
    "prompt": Unit.INPUT,
    "completion": Unit.OUTPUT,
    "input_cache_read": Unit.CACHED_INPUT,
    "audio": Unit.INPUT_AUDIO,
    "audio_output": Unit.OUTPUT_AUDIO,
    "image_token": Unit.INPUT_IMAGE,
    "image_output": Unit.OUTPUT_IMAGE,
}
SYNC_PRICES: Final = TaskDeclaration(
    name="ai.sync_prices",
    queue=TaskQueue.DEFAULT,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=2),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
SYNC_PRICES_JOB: Final = PeriodicJob(SYNC_PRICES, timedelta(days=1), homes=(Home.EU,))
LATEST = (
    select(ProviderPrice.model, ProviderPrice.unit, ProviderPrice.price_usd)
    .ext(distinct_on(ProviderPrice.model, ProviderPrice.unit))
    .where(ProviderPrice.provider == Provider.OPENROUTER.value)
    .where(ProviderPrice.effective_from <= func.now())
    .order_by(ProviderPrice.model, ProviderPrice.unit, ProviderPrice.effective_from.desc())
)
log = structlog.stdlib.get_logger(__name__)

type Prices = Mapping[tuple[str, Unit], Decimal]


def price(raw: object) -> Decimal | None:
    """A listed price as stored, or None when it is absent, malformed or negative."""
    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        return None
    if not value.is_finite() or value < 0:
        return None
    return value.quantize(PRICE_STEP)


def model_prices(
    model: str, pricing: Mapping[str, object], *, transcribes: bool
) -> Iterator[tuple[tuple[str, Unit], Decimal]]:
    """The unit prices of one listed model."""
    per_second = transcribes and not price(pricing.get("completion"))
    for field, listed_unit in FIELDS.items():
        value = price(pricing.get(field))
        if value is None or (per_second and field == "completion"):
            continue
        unit = Unit.AUDIO_SECOND if per_second and field == "prompt" else listed_unit
        if unit is Unit.AUDIO_SECOND and value > MAX_PER_SECOND:
            log.warning("Цена модели за секунду не читается: пропущена", model=model)
            continue
        yield (model, unit), value


def listed_prices(document: object) -> dict[tuple[str, Unit], Decimal]:
    """Every readable price of OpenRouter's model list, by model and unit."""
    rows = document.get("data") if isinstance(document, dict) else None
    listed: dict[tuple[str, Unit], Decimal] = {}
    for model in rows if isinstance(rows, list) else ():
        if not isinstance(model, dict):
            continue
        name, pricing = model.get("id"), model.get("pricing")
        if not isinstance(name, str) or not 0 < len(name) <= MODEL_NAME_MAX:
            continue
        if not isinstance(pricing, dict):
            continue
        architecture = model.get("architecture")
        outputs = architecture.get("output_modalities") if isinstance(architecture, dict) else None
        transcribes = isinstance(outputs, list) and "transcription" in outputs
        listed.update(model_prices(name, pricing, transcribes=transcribes))
    return listed


def changed(listed: Prices, in_force: Prices) -> dict[tuple[str, Unit], Decimal]:
    """The listed prices that differ from the ones in force or are new."""
    return {key: value for key, value in listed.items() if in_force.get(key) != value}


def price_sync_handler(
    transactions: HomeTransactions, client: httpx.AsyncClient, base_url: str = OPENROUTER_API
) -> TaskHandler[HomeTaskPayload]:
    """The sync task bound to the process's HTTP client."""
    url = base_url.rstrip("/") + "/models"

    async def sync(_payload: HomeTaskPayload) -> None:
        response = await client.get(
            url, params={"output_modalities": "all"}, timeout=FETCH_DEADLINE.total_seconds()
        )
        response.raise_for_status()
        listed = listed_prices(response.json())
        if not listed:
            log.error("Список моделей OpenRouter без цен: ничего не записано")
            return
        async with transactions.begin(TenancyScope(Home.EU)) as session:
            in_force = {
                (model, Unit(unit)): value
                for model, unit, value in (await session.execute(LATEST)).all()
            }
            fresh = changed(listed, in_force)
            if fresh:
                await session.execute(
                    insert(ProviderPrice).values(
                        [
                            {"id": new_id(), "provider": Provider.OPENROUTER.value, "model": model,
                             "unit": unit.value, "price_usd": value,
                             "effective_from": func.now(), "source": "openrouter"}
                            for (model, unit), value in fresh.items()
                        ]
                    )
                )  # fmt: skip
        log.info("Цены OpenRouter сверены", listed=len(listed), changed=len(fresh))

    return TaskHandler(SYNC_PRICES, sync)

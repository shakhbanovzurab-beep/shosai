"""A cost row before it is written: everything the writer and the deferred task carry."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from shosai.core.tasks.payloads import HomeTaskPayload


class CostEntry(HomeTaskPayload):
    """One paid call's row; also the payload of the deferred-record task (ids and numbers only).

    `home`, `user_id` and `org_id` are the payer's scope; `created_at` is the moment of the
    call, so a deferred row lands in the partition and at the prices of its call.
    """

    cost_id: UUID
    created_at: datetime
    effect_key: str
    platform_account: str | None = None
    provider: str
    model: str
    kind: str
    feature: str
    call_class: str
    origin: str
    outcome: str
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    input_audio_tokens: int = 0
    output_audio_tokens: int = 0
    units: Decimal = Decimal(0)
    unit: str | None = None
    cost_usd: Decimal
    cost_source: str
    exchange_rate_used: Decimal | None = None
    cost_rub: Decimal | None = None

"""The draft's request and response shapes of the native sign-in routes (D1 gate).

The macOS and Windows 1.4.5 clients decode these; the D1 gate compares every property,
its requiredness and its type with the draft's OpenAPI. Names, optionality and nullability
are the draft's, component names included where the gate reads them. Requests accept
unknown fields, as the draft did: refusing one would break a client that sends it.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Address and password; the captcha token when the sign-in page shows one."""

    email: Annotated[str, Field(min_length=3, max_length=254)]
    password: Annotated[str, Field(min_length=1, max_length=256)]
    captcha_token: Annotated[str | None, Field(max_length=4096)] = None


class TokenResponse(BaseModel):
    """A session: the access token, its lifetime in seconds and the CSRF value for refresh."""

    access_token: str
    expires_in: int
    token_type: str = Field(default="Bearer")
    csrf_token: str | None = None


class TariffDTO(BaseModel):
    """A plan of the catalogue, as the draft described it; billing fills it."""

    id: UUID
    code: str
    name: str
    price_rub: int
    period_days: int
    minutes_limit: int | None
    allow_knowledge_base: bool
    allow_multiscreenshot: bool
    allow_system_design: bool
    allow_frontier_models: bool
    is_active: bool
    currency: str = "RUB"
    price: float | None = None
    price_eur: float = 0.0
    price_usd: float = 0.0
    storage_limit_bytes: int | None = None


class SubscriptionCardDTO(BaseModel):
    """The person's subscription; billing fills it."""

    status: str
    tariff: TariffDTO | None
    started_at: datetime
    expires_at: datetime | None
    days_left: int | None
    bonus_minutes: int
    credits: float


class QuotaSnapshot(BaseModel):
    """Recording minutes left; billing fills it."""

    unlimited: bool
    limit_minutes: int | None
    bonus_minutes: int
    used_minutes: float | None
    remaining_minutes: float | None
    exhausted: bool


class FeaturesOut(BaseModel):
    """Capabilities of the plan; the draft's defaults until billing contributes."""

    voice_translation: bool = False
    voice: bool = False
    teleprompter: bool = False
    premium_weekly_remaining_pct: float | None = None
    premium_credit_usd: float = 0.0
    premium_credit_currency: str = "USD"
    premium_credit_amount: float = 0.0


class UserMeResponse(BaseModel):
    """The signed-in person as the desktop clients read it; all 23 fields are present."""

    id: UUID
    email: str
    username: str | None
    phone: str | None
    avatar_url: str | None
    role: str
    status: str
    is_active: bool
    last_login_at: datetime | None
    language: str | None
    timezone: str | None
    no_logs: bool
    meeting_auto_tasks: bool
    memory_enabled: bool
    leo_voice_enabled: bool
    leo_web_search_enabled: bool
    leo_kb_search_enabled: bool
    leo_connector_search_enabled: bool
    marketing_consent: bool
    appearance: dict[str, object]
    subscription: SubscriptionCardDTO | None
    quota: QuotaSnapshot | None
    features: FeaturesOut

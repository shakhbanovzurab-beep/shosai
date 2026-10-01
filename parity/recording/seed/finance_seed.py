"""Деньги в админке: оплаты персон, собственные расходы администратора на модели
и всплески токенов, на которые дашборд поднимает тревогу.

Раздел «Деньги» показывает расходы того администратора, который его открыл, —
поэтому у «Администратора» свои вызовы: 18 моделей у четырёх провайдеров за
месяц, три сегодня. Вместе с моделями «Руководителя» их больше 20 — у разбивки
дашборда есть вторая страница. Стоимости у моделей разные: разбивка сортируется
по ним, и равные база отдала бы в любом порядке.

Тревоги дашборда: «Семён» сжёг 200 тысяч токенов за последний час, у «Тимура»
за 10 минут в 60 раз больше обычного. Часы API стоят на моменте стенда, поэтому
окна «час» и «10 минут» не зависят от того, когда записан визит.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from meetassist.models import Transaction
from meetassist.models.provider_cost import ProviderCost
from meetassist.models.user import User
from meetassist.services.tariff_service import get_tariff_by_code
from sqlalchemy.ext.asyncio import AsyncSession

_RUB_PER_USD = Decimal("95")

#: Оплаты: персона, тариф, способ, статус, валюта, сумма в валюте, часов назад.
_PAYMENTS = (
    ("max", "max_1m", "cloudpayments", "success", "RUB", 3490, 240),
    ("quota", "pro_1m", "lava", "success", "RUB", 1990, 239),
    ("overquota", "pro_1m", "tbank", "success", "RUB", 1990, 238),
    ("sharer", "pro_1m", "moneta", "success", "RUB", 1990, 237),
    ("cheap", "pro_1m", "tbank", "success", "RUB", 1990, 236),
    ("trusted", "max_1m", "lava_paypal", "success", "USD", 47, 235),
    ("applicant", "start", "tbank", "failed", "RUB", 790, 26),
    ("declined", "pro_1m", "cloudpayments", "pending", "RUB", 1990, 3),
)

#: Модели администратора: провайдер, модель, роль, цена вызова в долларах.
_ADMIN_MODELS = (
    ("openrouter", "anthropic/claude-sonnet-5.5", "responses", "0.0410"),
    ("openrouter", "anthropic/claude-opus-5.5", "coding", "0.0930"),
    ("openrouter", "openai/gpt-5.1", "responses", "0.0350"),
    ("openrouter", "openai/gpt-5.1-mini", "generation", "0.0061"),
    ("openrouter", "google/gemini-3-pro-preview", "vision", "0.0280"),
    ("openrouter", "mistralai/mistral-large-3", "translation", "0.0122"),
    ("openrouter", "meta-llama/llama-4-maverick", "generation", "0.0047"),
    ("openrouter", "x-ai/grok-4", "responses", "0.0315"),
    ("openrouter", "qwen/qwen3-235b-a22b", "coding", "0.0083"),
    ("openrouter", "deepseek/deepseek-v4-pro", "coding", "0.0105"),
    ("openrouter", "moonshotai/kimi-k2", "generation", "0.0071"),
    ("openrouter", "z-ai/glm-4.6", "translation", "0.0058"),
    ("openrouter", "cohere/command-a", "generation", "0.0093"),
    ("perplexity", "sonar-pro", "search", "0.0162"),
    ("google", "gemini-live-2.5-flash", "voice", "0.0214"),
    ("google", "gemini-2.5-flash-tts", "voice", "0.0038"),
    ("deepgram", "nova-3", "transcription", "0.0186"),
    ("deepgram", "nova-3-diarize", "diarization", "0.0029"),
)


async def seed_finance(db: AsyncSession, accounts: dict[str, User], clock: datetime) -> None:
    """Засевает оплаты, расходы администратора и всплески токенов для тревог."""
    for key, code, method, status, currency, amount, hours in _PAYMENTS:
        user = accounts[key]
        tariff = await get_tariff_by_code(db, code)
        if tariff is None:
            raise RuntimeError(f"тарифа {code} нет в базе черновика")
        at = clock - timedelta(hours=hours)
        db.add(Transaction(user_id=user.id, tariff_id=tariff.id, tariff_code=code, currency=currency,
                           amount=Decimal(amount), amount_rub=tariff.price_rub, method=method, status=status,
                           external_id=f"parity-{user.email}-{code}-{method}",
                           paid_at=at if status == "success" else None, created_at=at))
    admin = accounts["admin"]
    for index in range(43):
        provider, model, role, price = _ADMIN_MODELS[index % len(_ADMIN_MODELS)]
        # Три вызова — сегодня, за два–пять часов до момента стенда; остальные — за месяц.
        moment = (clock - timedelta(hours=2 + index) if index < 3
                  else clock - timedelta(days=index % 29 + 1, hours=index % 9, minutes=index))
        _cost(db, admin, provider, model, role, Decimal(price) * (1 + index % 3), 2400 + 53 * index, 520 + 17 * index,
              moment)
    for minutes in (15, 25, 35, 45):
        _cost(db, accounts["abuser"], "openrouter", "x-ai/grok-4", "responses", Decimal("0.6200"), 42_000, 8_000,
              clock - timedelta(minutes=minutes))
    _cost(db, accounts["cheap"], "openrouter", "openai/gpt-5.1-mini", "generation", Decimal("0.0310"), 5_100, 900,
          clock - timedelta(minutes=4))
    for hours in range(3, 21, 3):
        _cost(db, accounts["cheap"], "openrouter", "openai/gpt-5.1-mini", "generation", Decimal("0.0140"), 2_000, 400,
              clock - timedelta(hours=hours))
    await db.flush()


def _cost(db: AsyncSession, user: User, provider: str, model: str, role: str, usd: Decimal, tokens_in: int,
          tokens_out: int, at: datetime) -> None:
    db.add(ProviderCost(user_id=user.id, provider=provider, model_name=model, role=role, input_tokens=tokens_in,
                        output_tokens=tokens_out, latency_ms=700 + tokens_out // 10, cost_usd=usd,
                        cost_rub=(usd * _RUB_PER_USD).quantize(Decimal("0.01")), exchange_rate_used=_RUB_PER_USD,
                        created_at=at))

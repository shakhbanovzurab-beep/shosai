"""Аккаунты персон: пользователь, подписка, обучение, сохранённая карта.

Пользователь создаётся служебной регистрацией черновика (`auth_service.register`) —
той же, что сидинг и тесты черновика. Она проставляет подписку Free и реферальный
код ровно так, как настоящая регистрация; засев потом только сдвигает состояние.
Случайные значения регистрации (реферальный код, моменты «сейчас») заменяются
явными: они видны на экранах и обязаны совпадать между записями.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from meetassist.models import RecurringPaymentMethod, UserOnboarding
from meetassist.models.recurring import RPM_ACTIVE
from meetassist.models.user import User
from meetassist.services.auth_service import register
from meetassist.services.tariff_service import change_tariff, get_subscription, get_tariff_by_code
from sqlalchemy.ext.asyncio import AsyncSession

from personas import PASSWORD, TIMEZONE, Persona

log = logging.getLogger("parity.seed")


async def create_account(
    db: AsyncSession, persona: Persona, clock: datetime, accounts: dict[str, User]
) -> User:
    """Создаёт аккаунт персоны со всем её состоянием."""
    user = await register(db, persona.email, PASSWORD, name=persona.name, language="ru")
    registered_at = clock - timedelta(days=persona.registered_days_ago)
    user.created_at = registered_at
    user.timezone = TIMEZONE
    user.referral_code = persona.referral_code
    user.role = persona.role
    user.status = persona.status
    user.ai_minutes_used = persona.minutes_used
    if persona.referred_by is not None:
        user.referred_by_user_id = accounts[persona.referred_by].id
    await _set_subscription(db, user, persona, clock, registered_at)
    if persona.onboarding is not None:
        db.add(_onboarding(user, persona, registered_at))
    if persona.saved_card:
        db.add(_saved_card(user, persona, registered_at))
    await db.flush()
    log.info(
        "персона %s создана, тариф %s",
        persona.key,
        persona.tariff,
        extra={"persona": persona.key, "tariff": persona.tariff},
    )
    return user


async def _set_subscription(
    db: AsyncSession, user: User, persona: Persona, clock: datetime, registered_at: datetime
) -> None:
    """Free — с момента регистрации, бессрочно; платный — с явными датами."""
    subscription = await get_subscription(db, user.id)
    if subscription is None:
        raise RuntimeError(f"регистрация не создала подписку персоне {persona.key}")
    if persona.tariff == "free":
        subscription.started_at = registered_at
        return
    tariff = await get_tariff_by_code(db, persona.tariff)
    if tariff is None:
        raise RuntimeError(f"тарифа {persona.tariff} нет в базе черновика")
    subscription = await change_tariff(db, user.id, tariff)
    subscription.started_at = clock - timedelta(days=persona.paid_days_ago)
    subscription.expires_at = subscription.started_at + timedelta(days=tariff.period_days)
    subscription.auto_renew = persona.saved_card


def _onboarding(user: User, persona: Persona, registered_at: datetime) -> UserOnboarding:
    completed = persona.onboarding == "completed"
    return UserOnboarding(
        user_id=user.id,
        status=persona.onboarding,
        version=1,
        current_step=persona.tour_step,
        completed_steps=[],
        done_actions=[],
        audio_status="declined",
        started_at=registered_at,
        completed_at=registered_at + timedelta(minutes=20) if completed else None,
        created_at=registered_at,
    )


def _saved_card(user: User, persona: Persona, registered_at: datetime) -> RecurringPaymentMethod:
    return RecurringPaymentMethod(
        user_id=user.id,
        provider="tbank",
        customer_key=f"parity-{persona.key}",
        card_mask="4242",
        card_exp="12/2027",
        card_brand="visa",
        status=RPM_ACTIVE,
        created_at=registered_at,
    )

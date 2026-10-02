"""Persona accounts: user, subscription, onboarding, saved card.

The user is created by the draft's internal registration (`auth_service.register`),
the same one the draft's seeding and tests use. It sets up the Free subscription and
the referral code exactly as a real sign-up does; the seed then only shifts the state.
The random values of registration (referral code, "now" timestamps) are replaced with
explicit ones: they are visible on screens and must match between recordings.
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
    """Create the persona's account with all of its state."""
    user = await register(db, persona.email, PASSWORD, name=persona.name, language="ru")
    # Минуты по порядку создания: список пользователей в админке сортируется
    # только по дате регистрации, и равные даты база отдала бы в любом порядке.
    registered_at = clock - timedelta(days=persona.registered_days_ago, minutes=len(accounts))
    user.created_at = registered_at
    # Рекордер входит за персону, и черновик ставит «последний вход» = сейчас.
    # Засеянное «сейчас» не зависит от того, какие визиты уже прошли.
    user.last_login_at = clock
    user.timezone = TIMEZONE
    user.referral_code = persona.referral_code
    user.role = persona.role
    user.status = persona.status
    # Черновик снимает активность при заморозке и бане (api/admin/users.py).
    user.is_active = persona.status == "active"
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
    """Free: from registration, with no end date; a paid tariff: with explicit dates."""
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
        completed_steps=list(persona.tour_steps),
        done_actions=list(persona.first_actions),
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

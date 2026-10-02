"""Persona surroundings: published client builds, payments and referral rewards.

Builds are visible to everyone, so their seed is shared. Payments and rewards belong to
personas: the payment history of `pro` and the reward of `free` for the payment `pro`
made.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from meetassist.models import AppBuild, ReferralReward, Transaction
from meetassist.models.referral_reward import REWARD_ACTIVE
from meetassist.models.transaction import TX_REFUNDED, TX_SUCCESS
from meetassist.models.user import User
from meetassist.services.tariff_service import get_tariff_by_code
from sqlalchemy.ext.asyncio import AsyncSession

#: Размеры — как у настоящих сборок: экран показывает их в мегабайтах.
#: Платформа, версия, файл, размер, опубликована, суток назад загружена. Список в
#: админке сортируется по времени загрузки, поэтому оно у всех разное; снятая
#: 1.4.4 видна только там.
_BUILDS = (
    ("macos", "1.4.5", "Whisperer-1.4.5.dmg", 89_438_208, True, 5),
    ("windows", "1.4.5", "Whisperer-Setup-1.4.5.exe", 74_235_904, True, 5.05),
    ("macos", "1.4.4", "Whisperer-1.4.4.dmg", 88_965_120, False, 26),
)


async def seed_world(db: AsyncSession, clock: datetime, accounts: dict[str, User]) -> None:
    """Seed the shared surroundings and the surroundings of the personas."""
    admin = accounts["admin"]
    for platform, version, file_name, size, current, days in _BUILDS:
        db.add(
            AppBuild(
                platform=platform,
                version=version,
                notes="Стабильность записи и новые горячие клавиши." if current else "Исправления звука на AirPods.",
                file_name=file_name,
                storage_name=f"parity-{platform}-{version}",
                size_bytes=size,
                is_current=current,
                published_at=clock - timedelta(days=5 if current else days),
                uploaded_by_user_id=admin.id,
                created_at=clock - timedelta(days=days),
            )
        )
    payment = await _payment(db, accounts["pro"], "pro_1m", clock - timedelta(days=10), TX_SUCCESS)
    await _payment(db, accounts["pro"], "start", clock - timedelta(days=40), TX_REFUNDED)
    await _payment(db, accounts["start"], "start", clock - timedelta(days=2), TX_SUCCESS)
    db.add(
        ReferralReward(
            referrer_id=accounts["free"].id,
            referred_user_id=accounts["pro"].id,
            transaction_id=payment.id,
            amount_rub=199,
            status=REWARD_ACTIVE,
            created_at=clock - timedelta(days=10),
        )
    )
    await db.flush()


async def _payment(
    db: AsyncSession, user: User, tariff_code: str, paid_at: datetime, status: str
) -> Transaction:
    tariff = await get_tariff_by_code(db, tariff_code)
    if tariff is None:
        raise RuntimeError(f"тарифа {tariff_code} нет в базе черновика")
    payment = Transaction(
        user_id=user.id,
        tariff_id=tariff.id,
        tariff_code=tariff.code,
        currency="RUB",
        amount=Decimal(tariff.price_rub),
        amount_rub=tariff.price_rub,
        method="tbank",
        status=status,
        external_id=f"parity-{user.email}-{tariff_code}",
        paid_at=paid_at,
        created_at=paid_at,
    )
    db.add(payment)
    await db.flush()
    return payment

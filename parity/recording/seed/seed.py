"""Засев стенда записи фикстур: персоны стенда сравнения и их окружение.

Запускается внутри образа API черновика на свежей промигрированной базе:

    python /seed/seed.py

Время процесса подменено libfaketime на момент стенда сравнения, поэтому всё, что
черновик ставит «сейчас», совпадает с замороженными часами браузера. Моменты в
прошлом и будущем засев задаёт явно, от того же момента (`PARITY_CLOCK`).

Засев работает только на пустой базе. Шаблон базы пересоздаёт record.sh при
любом изменении засева; непустая база — ошибка, а не повод досеять.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime

from meetassist.models.base import async_session_factory
from meetassist.models.user import User
from sqlalchemy import func, select

from accounts import create_account
from personas import PERSONAS
from world import seed_world

log = logging.getLogger("parity.seed")


def parity_clock() -> datetime:
    """Момент стенда сравнения из окружения; без него засев не запускается."""
    raw = os.environ.get("PARITY_CLOCK")
    if not raw:
        raise RuntimeError("PARITY_CLOCK не задан: засев запускается через record.sh")
    clock = datetime.fromisoformat(raw)
    if clock.tzinfo is None:
        raise RuntimeError(f"PARITY_CLOCK без часового пояса: {raw}")
    return clock.astimezone(UTC)


async def seed() -> None:
    clock = parity_clock()
    async with async_session_factory() as db:
        existing = await db.scalar(select(func.count(User.id)))
        if existing:
            raise RuntimeError(f"база не пуста: пользователей {existing}")
        accounts: dict[str, User] = {}
        for persona in PERSONAS:
            accounts[persona.key] = await create_account(db, persona, clock, accounts)
        await seed_world(db, clock, accounts)
        await db.commit()
    log.info("засев завершён: персон %d", len(accounts), extra={"personas": len(accounts)})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    asyncio.run(seed())

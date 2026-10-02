"""Seed of the fixture recording stand: the parity personas and their surroundings.

Runs inside the draft API image on a freshly migrated database:

    python /seed/seed.py

The process time is replaced by libfaketime with the parity clock, so everything the
draft stamps as "now" matches the browser's frozen clock. The seed sets past and future
timestamps explicitly, relative to the same moment (`PARITY_CLOCK`).

The seed works only on an empty database. record.sh recreates the database template on
any change to the seed; a non-empty database is an error, not a reason to seed more.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime

from meetassist.models.base import async_session_factory
from meetassist.models.user import User
from sqlalchemy import func, select

# Регистрирует все таблицы черновика: у засеваемых моделей внешние ключи на чужие.
import meetassist.composition.metadata  # noqa: F401
from accounts import create_account
from admin_seed import seed_admin
from analytics_seed import seed_analytics
from calendar_seed import seed_calendar
from files_seed import seed_files, set_storage_counters
from finance_seed import seed_finance
from hubs_seed import seed_hubs
from leo_cabinet import seed_leo_cabinet
from mcp_seed import seed_mcp
from meetings import seed_meetings
from personas import PERSONAS
from prompts_models import seed_prompts_models
from rooms_seed import seed_rooms
from satisfaction_seed import seed_satisfaction
from security_seed import seed_security
from streams_seed import seed_streams
from studio import seed_studio
from support_seed import seed_support
from tracker_seed import seed_boards, seed_tracker
from workspace import seed_workspace
from world import seed_world

log = logging.getLogger("parity.seed")


def parity_clock() -> datetime:
    """The parity clock from the environment; the seed does not run without it."""
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
        lead = accounts["lead"]
        sessions = await seed_meetings(db, lead, clock)
        await seed_workspace(db, lead, clock, sessions)
        boards = await seed_boards(db, lead, clock)
        await seed_hubs(db, lead, clock, sessions, {key: columns[""] for key, columns in boards.items()})
        await seed_tracker(db, lead, clock, boards)
        await seed_calendar(db, lead, clock, sessions)
        await seed_studio(db, lead, clock)
        await seed_leo_cabinet(db, lead, clock)
        await seed_mcp(db, lead, clock)
        await seed_prompts_models(db, lead, accounts["admin"], clock)
        await seed_rooms(db, lead, accounts["admin"], clock)
        await seed_streams(db, accounts, clock)
        await seed_files(db, lead, clock)
        await seed_support(db, accounts)
        await seed_satisfaction(db, accounts, clock)
        await seed_security(db, accounts, clock)
        await seed_admin(db, accounts, clock)
        await seed_finance(db, accounts, clock)
        events = await seed_analytics(db)
        # Последним: счётчик занятого места — сумма всех файлов «руководителя».
        await set_storage_counters(db, accounts, clock)
        await db.commit()
    log.info("засев завершён: персон %d, событий аналитики %d", len(accounts), events,
             extra={"personas": len(accounts), "analytics_events": events})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    asyncio.run(seed())

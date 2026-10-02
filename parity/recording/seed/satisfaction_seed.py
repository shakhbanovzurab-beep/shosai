"""Satisfaction surveys over the last 112 days.

One person's displays are at least 20 days apart: that is how the draft issues them.
The breakdowns (gender, OS, country, tariff, language) produce no tied rows in the
report: the database does not guarantee the order of ties. No timestamp lies within an
hour of the edges of the 30, 90, 180 and 365 day windows.

Every persona used by visits has seen the survey recently, so the draft answers it with
"too early" and writes nothing itself. Only `exhausted` can get the survey (its last
display was 38 days ago).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from meetassist.features.satisfaction.infrastructure.models import SatisfactionSurvey
from meetassist.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

#: Персона, суток до момента стенда, час, минута, оценка (None — без ответа),
#: закрыта не ответив, ОС, страна, язык, тариф, пол, источник пола.
_SURVEYS = (
    ("lead", 112, 10, 15, 4, False, "macos", "RU", "ru", "free", "female", "model"),
    ("lead", 88, 14, 40, 5, False, "macos", "RU", "ru", "free", "female", "model"),
    ("lead", 66, 9, 5, None, True, "ios", "RU", "ru", "free", "female", "model"),
    ("lead", 45, 16, 20, 4, False, "macos", "RU", "ru", "free", "female", "model"),
    ("lead", 24, 11, 30, 5, False, "macos", "RU", "en", "free", "female", "model"),
    ("lead", 3, 13, 10, 5, False, "macos", "RU", "ru", "pro_1m", "female", "model"),
    ("free", 40, 10, 0, 3, False, "macos", "RU", "ru", "free", "female", "model"),
    ("free", 12, 15, 30, 4, False, "windows", "RU", "ru", "free", "female", "model"),
    ("tour", 19, 17, 45, None, True, "android", "RU", "ru", "free", "female", "model"),
    ("exhausted", 38, 8, 50, 2, False, "windows", "KZ", "ru", "free", "male", "model"),
    ("start", 36, 12, 30, 5, False, "ios", "RU", "ru", "free", "female", "model"),
    ("start", 1, 9, 40, 4, False, "ios", "RU", "ru", "start", "female", "name"),
    ("pro", 41, 11, 0, 4, False, "linux", "DE", "en", "free", "male", "model"),
    ("pro", 8, 18, 5, 5, False, "linux", "DE", "en", "pro_1m", "male", "model"),
    ("max", 27, 14, 15, 3, False, "macos", "BY", "ru", "free", "female", "model"),
    ("max", 6, 10, 30, None, False, "macos", "BY", "ru", "max_1m", "female", "model"),
    ("admin", 33, 10, 0, 5, False, "macos", "RU", "ru", "free", "unknown", "model"),
    ("admin", 5, 16, 0, 4, False, "macos", "RU", "ru", "free", "unknown", "none"),
    ("banned", 34, 13, 20, 1, False, "windows", "KZ", "ru", "free", "male", "model"),
    ("editor", 39, 9, 30, None, True, "windows", "RU", "ru", "free", "female", "model"),
    ("editor", 14, 12, 45, 2, False, "windows", "", "ru", "free", "female", "model"),
    ("quota", 17, 15, 0, 3, False, "android", "KZ", "ru", "free", "male", "model"),
    ("overquota", 9, 11, 20, None, True, "other", "US", "en", "pro_1m", "female", "model"),
)


async def seed_satisfaction(db: AsyncSession, accounts: dict[str, User], clock: datetime) -> None:
    """Seed survey displays with answers, dismissals and one display without an outcome."""
    day = clock.replace(hour=0, minute=0, second=0, microsecond=0)
    for key, days, hour, minute, score, dismissed, platform, country, language, plan, gender, source in _SURVEYS:
        user = accounts[key]
        shown = day - timedelta(days=days) + timedelta(hours=hour, minutes=minute)
        status = "answered" if score is not None else "dismissed" if dismissed else "shown"
        db.add(SatisfactionSurvey(
            user_id=user.id, status=status, score=score,
            answered_at=shown + timedelta(minutes=2) if score is not None else None,
            language=language, plan=plan, country=country, platform=platform, gender=gender, gender_source=source,
            is_internal=user.role == "admin", created_at=shown,
            updated_at=shown + timedelta(minutes=2) if status != "shown" else None,
        ))
    await db.flush()

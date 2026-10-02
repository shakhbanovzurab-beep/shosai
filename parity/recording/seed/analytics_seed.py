"""Product analytics events: four and a half months of the product's life.

The draft computes product analytics on request from the events table; in production
the table is filled by the clients and the fact bus. Here a simulation produces the
events: every day landing visitors arrive, some of them sign up, install the desktop
client and grant permissions; registered people come back with a decaying probability,
hold meetings, copy answers, hit the limit and open checkout.

The generator is deterministic: the seed is fixed, and the traversal order is by day
and by person. Simulated people are not draft accounts: their ids exist only in events.

Thursday, July 16 is the last closed day. On it there are three times fewer meetings on
macOS 1.4.5 than usual and a spike of aborts: this produces findings, fired alerts and
lagging targets. There are no events for today: the recording visits write them.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from meetassist.features.analytics.infrastructure.models import AnalyticsEvent
from meetassist.features.analytics.infrastructure.repository import ensure_partitions
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

_FIRST_DAY = date(2026, 3, 1)
_LAST_DAY = date(2026, 7, 16)
_INCIDENT = date(2026, 7, 16)
_BATCH = 2_000

#: Категория и источник событий — по каталогу черновика (domain/catalog.py).
_CATEGORY = {
    "landing_viewed": ("registration", "client"), "signup_started": ("registration", "client"),
    "signup_completed": ("registration", "server"), "pricing_viewed": ("registration", "client"),
    "download_page_viewed": ("desktop", "client"), "app_installed": ("desktop", "client"),
    "app_first_launch": ("desktop", "client"), "app_permission_requested": ("desktop", "client"),
    "app_permission_granted": ("desktop", "client"), "meeting_started": ("meetings", "client"),
    "meeting_ended": ("meetings", "client"), "meeting_aborted": ("meetings", "client"),
    "shared_page_viewed": ("meetings", "client"), "shared_page_cta_clicked": ("meetings", "client"),
    "ai_answer_copied": ("ai", "client"), "ai_answer_rated": ("ai", "client"),
    "paywall_viewed": ("billing", "client"), "checkout_opened": ("billing", "client"),
    "feature_used": ("product", "client"),
}
#: Срезы: значения и их веса.
_PLATFORMS = (("macos", 50), ("windows", 34), ("web", 11), ("linux", 5))
_COUNTRIES = (("RU", 68), ("KZ", 11), ("BY", 8), ("DE", 8), ("US", 5))
_SOURCES = (("google", 34), ("yandex", 30), ("telegram", 16), ("", 20))
_FEATURES = (("meetings", 30), ("ai_copilot", 24), ("knowledge", 12), ("calendar", 12), ("tracker", 9),
             ("billing", 5), ("desktop", 8))


def _version(day: date) -> str:
    return "1.4.5" if day >= date(2026, 7, 12) else "1.4.4" if day >= date(2026, 6, 21) else "1.4.3"


def _pick(rng: random.Random, options: tuple[tuple[str, int], ...]) -> str:
    return rng.choices([value for value, _ in options], weights=[weight for _, weight in options])[0]


@dataclass
class _Person:
    anonymous_id: uuid.UUID
    user_id: uuid.UUID
    joined: date
    platform: str
    country: str
    utm: str
    plan: str = "free"
    #: Склонность возвращаться: у части людей продукт не прижился.
    loyalty: float = 0.5
    installed: bool = False


@dataclass
class _Writer:
    rng: random.Random
    rows: list[dict[str, Any]] = field(default_factory=list)

    def uid(self) -> uuid.UUID:
        return uuid.UUID(int=self.rng.getrandbits(128), version=4)

    def add(self, name: str, at: datetime, anonymous_id: uuid.UUID, *, person: _Person | None = None,
            session: uuid.UUID | None = None, platform: str = "web", country: str = "RU", feature: str = "",
            utm: str = "") -> None:
        category, source = _CATEGORY[name]
        utm = person.utm if person is not None else utm
        platform = person.platform if person is not None else platform
        country = person.country if person is not None else country
        native = platform in ("macos", "windows", "linux")
        self.rows.append({
            "ts": at, "event_id": self.uid(), "name": name, "category": category, "version": 1,
            "anonymous_id": anonymous_id, "user_id": person.user_id if person is not None else None,
            "session_id": session, "source": source, "platform": platform,
            "app_version": _version(at.date()) if native else "", "language": "en" if country in ("DE", "US") else "ru",
            "country": country, "plan": person.plan if person is not None else "", "feature": feature,
            "utm_source": utm, "utm_medium": "cpc" if utm in ("google", "yandex") else "",
            "utm_campaign": "", "referrer_domain": "", "sample_rate": 1.0, "is_internal": False, "ts_client": at,
            "clock_skew_ms": 0, "props": {"feature": feature} if feature else {},
        })


def _moment(rng: random.Random, day: date, start_hour: int = 7, end_hour: int = 20) -> datetime:
    seconds = rng.randrange(start_hour * 3600, end_hour * 3600)
    return datetime(day.year, day.month, day.day, tzinfo=UTC) + timedelta(seconds=seconds)


def _arrivals(writer: _Writer, day: date, people: list[_Person]) -> None:
    """Landing visitors; some of them sign up and install the client."""
    rng = writer.rng
    weekend = day.weekday() >= 5
    for _ in range(rng.randint(70, 85) if weekend else rng.randint(135, 160)):
        anonymous_id, utm = writer.uid(), _pick(rng, _SOURCES)
        country = _pick(rng, _COUNTRIES)
        at = _moment(rng, day)
        writer.add("landing_viewed", at, anonymous_id, country=country, utm=utm)
        if rng.random() > 0.21:
            continue
        writer.add("signup_started", at + timedelta(minutes=2), anonymous_id, country=country, utm=utm)
        if rng.random() > 0.78:
            continue
        person = _Person(anonymous_id, writer.uid(), day, _pick(rng, _PLATFORMS), country, utm,
                         loyalty=rng.betavariate(2, 3))
        people.append(person)
        writer.add("signup_completed", at + timedelta(minutes=5), anonymous_id, person=person)
        if person.platform != "web" and rng.random() < 0.8:
            _install(writer, person, at + timedelta(minutes=12))


def _install(writer: _Writer, person: _Person, at: datetime) -> None:
    rng = writer.rng
    writer.add("download_page_viewed", at, person.anonymous_id, person=person)
    if rng.random() > 0.86:
        return
    writer.add("app_installed", at + timedelta(minutes=4), person.anonymous_id, person=person)
    person.installed = True
    if rng.random() > 0.93:
        return
    writer.add("app_first_launch", at + timedelta(minutes=6), person.anonymous_id, person=person)
    writer.add("app_permission_requested", at + timedelta(minutes=7), person.anonymous_id, person=person)
    if rng.random() < 0.74:
        writer.add("app_permission_granted", at + timedelta(minutes=8), person.anonymous_id, person=person)


def _activity(writer: _Writer, day: date, person: _Person) -> None:
    """One active day of a person: meetings, answers, features, the limit and checkout."""
    rng = writer.rng
    session = writer.uid()
    at = _moment(rng, day, 8, 19)
    incident = day == _INCIDENT and person.platform == "macos"
    for _ in range(rng.choices((0, 1, 2), weights=(35, 50, 15))[0]):
        if incident and rng.random() < 0.7:
            continue
        writer.add("meeting_started", at, person.anonymous_id, person=person, session=session, feature="meetings")
        outcome = rng.random()
        aborted = outcome < (0.35 if incident else 0.03)
        ended = not aborted and outcome < 0.965
        if aborted:
            writer.add("meeting_aborted", at + timedelta(minutes=rng.randint(2, 9)), person.anonymous_id,
                       person=person, session=session)
        elif ended:
            writer.add("meeting_ended", at + timedelta(minutes=rng.randint(15, 70)), person.anonymous_id,
                       person=person, session=session)
            if rng.random() < 0.55:
                writer.add("ai_answer_copied", at + timedelta(minutes=rng.randint(5, 14)), person.anonymous_id,
                           person=person, session=session, feature="ai_copilot")
            if rng.random() < 0.2:
                writer.add("ai_answer_rated", at + timedelta(minutes=16), person.anonymous_id, person=person,
                           session=session, feature="ai_copilot")
        at += timedelta(minutes=80)
    for _ in range(rng.randint(1, 3)):
        writer.add("feature_used", at, person.anonymous_id, person=person, session=session,
                   feature=_pick(rng, _FEATURES))
        at += timedelta(minutes=7)
    if person.plan == "free" and rng.random() < 0.12:
        writer.add("paywall_viewed", at, person.anonymous_id, person=person, session=session, feature="billing")
        if rng.random() < 0.45:
            writer.add("pricing_viewed", at + timedelta(minutes=1), person.anonymous_id, person=person, session=session)
            if rng.random() < 0.22:
                writer.add("checkout_opened", at + timedelta(minutes=3), person.anonymous_id, person=person,
                           session=session, feature="billing")
                person.plan = "pro"


def _shared_pages(writer: _Writer, day: date, people: list[_Person]) -> None:
    """Views of public meeting results: some of the guests sign up."""
    rng = writer.rng
    for _ in range(rng.randint(12, 24)):
        anonymous_id = writer.uid()
        at = _moment(rng, day)
        writer.add("shared_page_viewed", at, anonymous_id, country=_pick(rng, _COUNTRIES))
        if rng.random() < 0.18:
            writer.add("shared_page_cta_clicked", at + timedelta(minutes=1), anonymous_id)
            if rng.random() < 0.4:
                person = _Person(anonymous_id, writer.uid(), day, "web", "RU", "", loyalty=rng.betavariate(2, 3))
                people.append(person)
                writer.add("signup_completed", at + timedelta(minutes=4), anonymous_id, person=person)
                writer.add("meeting_started", at + timedelta(minutes=20), anonymous_id, person=person,
                           feature="meetings")


def _events() -> list[dict[str, Any]]:
    writer = _Writer(random.Random(20260717))
    people: list[_Person] = []
    day = _FIRST_DAY
    while day <= _LAST_DAY:
        _arrivals(writer, day, people)
        _shared_pages(writer, day, people)
        weekend = day.weekday() >= 5
        for person in people:
            age = (day - person.joined).days
            if age <= 0:
                continue
            chance = person.loyalty * 0.55 * (age + 1) ** -0.32 * (0.55 if weekend else 1.0)
            if writer.rng.random() < chance:
                _activity(writer, day, person)
        day += timedelta(days=1)
    return writer.rows


async def seed_analytics(db: AsyncSession) -> int:
    """Create the March to July partitions, insert the events in batches, return their count."""
    await ensure_partitions(db, lookahead_months=4, now=datetime(2026, 3, 15, tzinfo=UTC))
    rows = _events()
    for start in range(0, len(rows), _BATCH):
        await db.execute(insert(AnalyticsEvent), rows[start:start + _BATCH])
    return len(rows)

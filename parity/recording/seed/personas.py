"""Personas of the parity stand: draft users on whose behalf the fixtures are recorded.

A persona describes the state of an account, not a screen: the tariff, the onboarding
step, who invited whom. A screen picks its persona in the visit definition
(src/recording/visits).

A visit that changes data gets its own persona. The draft API's in-process caches are
per user, and a change made by one visit must not leak into another one recorded in the
same run.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Общий пароль персон локального стенда. Не секрет: стенд одноразовый, живёт во
#: внутренней сети без выхода наружу, а сам пароль нужен рекордеру для входа.
PASSWORD = "parity-password-1"
EMAIL_DOMAIN = "parity.test"
TIMEZONE = "Europe/Moscow"


@dataclass(frozen=True)
class Persona:
    """The state of one draft account."""

    key: str
    name: str
    referral_code: str
    #: Сколько дней назад зарегистрирован, от момента стенда сравнения.
    registered_days_ago: int = 46
    tariff: str = "free"
    #: Сколько дней назад началась платная подписка; срок — период тарифа.
    paid_days_ago: int = 10
    role: str = "user"
    status: str = "active"
    #: Статус обучения; None — записи нет, обучение ещё не начиналось.
    onboarding: str | None = "completed"
    tour_step: str | None = None
    minutes_used: float = 12.0
    referred_by: str | None = None
    #: Сохранённая карта и включённое автопродление.
    saved_card: bool = False
    #: Пройденные шаги тура и первые действия — для воронки онбординга в админке.
    tour_steps: tuple[str, ...] = ()
    first_actions: tuple[str, ...] = ()

    @property
    def email(self) -> str:
        return f"{self.key}@{EMAIL_DOMAIN}"


PERSONAS: tuple[Persona, ...] = (
    Persona("free", "Анна Смирнова", "ANNA2026"),
    Persona("new", "Борис Котов", "BORIS2026", registered_days_ago=0, onboarding=None, minutes_used=0),
    Persona("tour", "Вера Лебедева", "VERA2026", onboarding="active", tour_step="map"),
    Persona("exhausted", "Глеб Орлов", "GLEB2026", minutes_used=60),
    Persona("start", "Дарья Новикова", "DARIA2026", tariff="start", paid_days_ago=2, referred_by="free"),
    Persona("pro", "Егор Волков", "EGOR2026", tariff="pro_1m", referred_by="free", saved_card=True),
    Persona("max", "Жанна Морозова", "ZHANNA2026", tariff="max_1m"),
    Persona("admin", "Администратор", "ADMIN2026", role="admin", onboarding=None),
    Persona("banned", "Илья Зайцев", "ILYA2026", status="banned"),
    Persona("editor", "Карина Белова", "KARINA2026"),
    #: Квоты файлов: 92 % тарифа Pro и перебор (files_seed.py).
    Persona("quota", "Олег Зуев", "OLEG2026", tariff="pro_1m"),
    Persona("overquota", "Полина Ершова", "POLINA2026", tariff="pro_1m"),
    #: Рабочее пространство целиком: встречи, календарь, контекст, база знаний.
    Persona("lead", "Мария Соколова", "MARIA2026", registered_days_ago=120, tariff="pro_1m", paid_days_ago=10),
    #: Админка (admin_seed.py, security_seed.py): замороженный аккаунт, шеринг
    #: аккаунта с разных IP, очередь abuse, партнёрская программа. Визитов у них нет.
    #: Пятеро зарегистрированы за последний месяц: их обучение — воронка дашборда.
    Persona("frozen", "Лев Фомин", "LEV2026", status="frozen", registered_days_ago=25,
            tour_steps=("map", "search", "agent", "analytics", "meetings"), first_actions=("first_question",)),
    Persona("sharer", "Никита Гусев", "NIKITA2026", tariff="pro_1m", registered_days_ago=75),
    Persona("sharer2", "Роман Титов", "ROMAN2026", registered_days_ago=9, onboarding="active", tour_step="agent",
            tour_steps=("map", "search"), first_actions=("first_question", "context_filled")),
    Persona("abuser", "Семён Мухин", "SEMEN2026", registered_days_ago=27,
            tour_steps=("map", "search", "agent", "analytics", "hub", "meetings", "audio-upload"),
            first_actions=("first_question", "first_prompt", "first_meeting", "desktop_downloaded")),
    Persona("cheap", "Тимур Ахмедов", "TIMUR2026", tariff="pro_1m", registered_days_ago=52),
    Persona("trusted", "Ульяна Крылова", "ULYANA2026", tariff="max_1m", registered_days_ago=88),
    Persona("blogger", "Филипп Рябов", "FILIPP2026", registered_days_ago=95),
    Persona("applicant", "Эмилия Цветкова", "EMILIA2026", registered_days_ago=21,
            tour_steps=("map", "search", "agent"), first_actions=("first_upload",)),
    Persona("declined", "Юрий Шестаков", "YURI2026", registered_days_ago=18, onboarding="skipped",
            tour_steps=("map",)),
)

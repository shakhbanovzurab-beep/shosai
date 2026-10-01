"""Персоны стенда сравнения: пользователи черновика, от имени которых пишутся фикстуры.

Персона описывает состояние аккаунта, а не экран: тариф, шаг обучения, кто кого
пригласил. Экран выбирает персону в определении визита (src/recording/visits).

Визит, который меняет данные, получает свою персону. Внутрипроцессные кэши API
черновика привязаны к пользователю, и изменение одного визита не должно
просочиться в другой, записанный в том же прогоне.
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
    """Состояние одного аккаунта черновика."""

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
    #: Рабочее пространство целиком: встречи, календарь, контекст, база знаний.
    Persona("lead", "Мария Соколова", "MARIA2026", registered_days_ago=120, tariff="pro_1m", paid_days_ago=10),
)

"""What the owner reads about a business event: ids, numbers and a link, nothing personal.

The monitoring channel is a Telegram chat (F5-D5): no email, name or text of the person
reaches it, only what the event carries — ids, amounts, a day — and a link to the account's
card in the admin panel, where the admin reads the rest. Each kind has a section in the
alerts runbook. The texts are plain Russian for the owner, like the other alerts.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Final
from uuid import UUID

MICRO_USD_PER_USD: Final = Decimal(1_000_000)
CENTS: Final = Decimal("0.01")


class Severity(StrEnum):
    """The class of the alert (F5-D4): a silent ticket or a notice batched by kind."""

    TICKET = "ticket"
    NOTICE = "notice"


@dataclass(frozen=True, slots=True)
class BusinessAlert:
    """One alert about one event: its kind, class, texts, runbook anchor and the admin card."""

    # Тип события — метка kind: по ней Alertmanager собирает уведомления в пачку.
    kind: str
    # Имя алерта — метка alertname; в сообщение не попадает.
    name: str
    severity: Severity
    summary: str
    description: str
    runbook: str
    admin_card: str


def admin_card(site: str, user_id: UUID) -> str:
    """The address of the account's card in the admin panel."""
    return f"{site.rstrip('/')}/admin/users/{user_id}"


def dollars(micro_usd: int) -> str:
    """An amount in millionths of a dollar as the owner reads it: «12,40 $»."""
    amount = (Decimal(micro_usd) / MICRO_USD_PER_USD).quantize(CENTS, rounding=ROUND_HALF_UP)
    return f"{amount:,.2f}".replace(",", " ").replace(".", ",") + " $"


def spend_exceeded(
    site: str, user_id: UUID, day: date, spend_micro_usd: int, threshold_micro_usd: int
) -> BusinessAlert:
    """A person's AI spend for a day passed the threshold: a ticket to look at the account."""
    return BusinessAlert(
        kind="ai.user_spend.exceeded",
        name="UserSpendExceeded",
        severity=Severity.TICKET,
        summary=(
            f"Один человек потратил на ИИ за {day:%d.%m} {dollars(spend_micro_usd)} "
            f"при пороге {dollars(threshold_micro_usd)}"
        ),
        description=(
            "Так бывает при злоупотреблении или зациклившемся запросе. Откройте карточку "
            "человека: там видно, на что ушли деньги. Если это злоупотребление, заблокируйте "
            "аккаунт там же. Следующее сообщение об этом человеке — не раньше завтрашнего дня."
        ),
        runbook="user-spend-exceeded",
        admin_card=admin_card(site, user_id),
    )


def account_deleted(site: str, user_id: UUID) -> BusinessAlert:
    """Every owner erased a person's data: a notice for the record."""
    return BusinessAlert(
        kind="identity.account.deleted",
        name="AccountDeleted",
        severity=Severity.NOTICE,
        summary="Аккаунт удалён по просьбе человека",
        description=(
            "Неделя после просьбы прошла, все данные человека стёрты, аккаунт обезличен. "
            "Делать ничего не нужно: сообщение для сведения."
        ),
        runbook="account-deleted",
        admin_card=admin_card(site, user_id),
    )


def sales_inquiry(site: str, user_id: UUID, team_size: str) -> BusinessAlert:
    """A person asked sales about a custom-priced plan: a notice to answer them."""
    return BusinessAlert(
        kind="billing.sales_inquiry.received",
        name="SalesInquiryReceived",
        severity=Severity.NOTICE,
        summary=f"Новая заявка в отдел продаж: команда {team_size} человек",
        description=(
            "Человек спросил о тарифе с ценой по договорённости. Рабочая почта, компания и "
            "сообщение хранятся в его доме; ответьте ему по почте из заявки."
        ),
        runbook="sales-inquiry-received",
        admin_card=admin_card(site, user_id),
    )


# Названия уровней моделей для владельца; ключи — значения уровней studio.
TIER_NAMES: Final = {"standard": "стандартный", "frontier": "frontier"}


def ai_models_screen(site: str) -> str:
    """The address of the AI models screen in the admin panel."""
    return f"{site.rstrip('/')}/admin/ai-models"


def model_unlisted(site: str, model_id: str) -> BusinessAlert:
    """OpenRouter no longer lists a model of the catalogue: it was switched off."""
    return BusinessAlert(
        kind="studio.model.disabled",
        name="StudioModelUnlisted",
        severity=Severity.TICKET,
        summary=f"OpenRouter убрал модель {model_id}: она выключена в каталоге",
        description=(
            "Ежедневная сверка не нашла модель в списке OpenRouter и выключила её. Люди, которые "
            "её выбрали, отвечают моделью роли по умолчанию. Если модель переименовали, добавьте "
            "её новый id на экране AI-моделей; сама она не включится."
        ),
        runbook="studio-model-unlisted",
        admin_card=ai_models_screen(site),
    )


def model_tier_proposed(site: str, model_id: str, confirmed: str, proposed: str) -> BusinessAlert:
    """A model's price proposes another tier: a ticket to confirm or decline it."""
    was, would = TIER_NAMES.get(confirmed, confirmed), TIER_NAMES.get(proposed, proposed)
    return BusinessAlert(
        kind="studio.model.tier_proposed",
        name="StudioTierProposed",
        severity=Severity.TICKET,
        summary=f"Цена модели {model_id} предлагает уровень {would} вместо уровня {was}",
        description=(
            "Цена выхода модели пересекла линию уровня. Пока предложение не подтверждено, модель "
            "считается в прежнем уровне — в лимитах людей и в расходах. Подтвердите или отклоните "
            "его на экране AI-моделей; уже списанное не пересчитывается."
        ),
        runbook="studio-tier-proposed",
        admin_card=ai_models_screen(site),
    )

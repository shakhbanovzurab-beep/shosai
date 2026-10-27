"""What the owner reads about a business event: amounts, a day and a link, nothing personal."""

import re
import uuid
from datetime import date
from pathlib import Path

import pytest

from shosai.features.alerting.domain.alerts import (
    BusinessAlert,
    Severity,
    account_deleted,
    dollars,
    model_tier_proposed,
    model_unlisted,
    sales_inquiry,
    spend_exceeded,
)

SITE = "https://shosai.tech/"
USER_ID = uuid.UUID("0190f0f0-0000-7000-8000-0000000000a1")
RUNBOOK = Path(__file__).parents[4] / "docs" / "runbooks" / "alerts.md"
# Всё, что похоже на адрес почты или имя: в чате мониторинга этого быть не должно (F5-D5).
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def every_alert() -> list[BusinessAlert]:
    """One alert of each kind."""
    return [
        spend_exceeded(SITE, USER_ID, date(2026, 10, 16), 23_456_789, 20_000_000),
        account_deleted(SITE, USER_ID),
        sales_inquiry(SITE, USER_ID, "51-200"),
        model_unlisted(SITE, "anthropic-claude-sonnet-5"),
        model_tier_proposed(SITE, "anthropic-claude-sonnet-5", "standard", "frontier"),
    ]


@pytest.mark.parametrize(
    ("micro_usd", "text"),
    [(0, "0,00 $"), (4_999, "0,00 $"), (5_000, "0,01 $"), (23_456_789, "23,46 $"),
     (1_234_500_000, "1 234,50 $")],
)  # fmt: skip
def test_an_amount_reads_in_dollars_and_cents_with_a_comma(micro_usd: int, text: str) -> None:
    assert dollars(micro_usd) == text


def test_the_spend_ticket_names_the_day_the_spend_and_the_threshold() -> None:
    alert = spend_exceeded(SITE, USER_ID, date(2026, 10, 16), 23_456_789, 20_000_000)

    assert alert.severity is Severity.TICKET
    assert alert.kind == "ai.user_spend.exceeded"
    assert alert.summary == "Один человек потратил на ИИ за 16.10 23,46 $ при пороге 20,00 $"
    assert alert.admin_card == f"https://shosai.tech/admin/users/{USER_ID}"


def test_a_deletion_is_a_notice_with_the_card_of_the_anonymised_account() -> None:
    alert = account_deleted("https://shosai.tech", USER_ID)

    assert alert.severity is Severity.NOTICE
    assert alert.kind == "identity.account.deleted"
    assert alert.admin_card == f"https://shosai.tech/admin/users/{USER_ID}"


@pytest.mark.parametrize("alert", every_alert(), ids=lambda alert: alert.kind)
def test_an_alert_carries_an_id_and_numbers_only(alert: BusinessAlert) -> None:
    texts = " ".join((alert.summary, alert.description, alert.admin_card))

    assert not EMAIL.search(texts)
    assert str(USER_ID) not in alert.summary + alert.description


@pytest.mark.parametrize("alert", every_alert(), ids=lambda alert: alert.kind)
def test_every_kind_has_its_section_in_the_runbook(alert: BusinessAlert) -> None:
    assert f'<a id="{alert.runbook}"></a>' in RUNBOOK.read_text(encoding="utf-8")


def test_a_catalogue_ticket_names_the_model_and_opens_the_ai_models_screen() -> None:
    alert = model_tier_proposed(SITE, "google-gemini-3-8-flash", "standard", "frontier")

    assert alert.severity is Severity.TICKET
    assert "google-gemini-3-8-flash" in alert.summary
    assert "frontier" in alert.summary
    assert alert.admin_card == "https://shosai.tech/admin/ai-models"

"""Declarations and payloads: explicit names, bounded deadlines, retries only where they help."""

from datetime import timedelta
from uuid import UUID

import pytest
from pydantic import SecretStr, ValidationError

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.tasks.declaration import (
    HOLD_GRACE,
    MAX_DELIVERIES,
    NO_RETRY,
    RETRY_TRANSIENT,
    RetryPolicy,
    TaskDeclaration,
    TaskKind,
)
from shosai.core.tasks.payloads import MASK_SECRETS
from shosai.core.tasks.queues import TaskQueue
from tests.core.tasks.workbench import HomeProbe, Probe, declare

USER_ID = UUID("01920000-0000-7000-8000-000000000001")
ORG_ID = UUID("01920000-0000-7000-8000-000000000002")
RECORD_ID = UUID("01920000-0000-7000-8000-000000000003")


@pytest.mark.parametrize(
    "name",
    ["send_email", "Mail.send", "mail.", "mail..send", "mail.send-email", "m" * 60 + ".send"],
)
def test_a_task_name_is_slice_dot_task_in_snake_case(name: str) -> None:
    with pytest.raises(ValueError, match="имя задачи"):
        declare(name)


def test_a_name_may_have_several_parts() -> None:
    assert declare("messaging.relay_outbox.ru").name == "messaging.relay_outbox.ru"


@pytest.mark.parametrize("deadline", [timedelta(0), timedelta(seconds=-1), timedelta(hours=2)])
def test_a_deadline_is_positive_and_at_most_an_hour(deadline: timedelta) -> None:
    with pytest.raises(ValueError, match="дедлайн"):
        declare("probe.deadline", deadline=deadline)


def test_the_hold_limit_is_the_deadline_with_a_grace() -> None:
    task = declare("probe.hold", deadline=timedelta(seconds=30))

    assert task.hold_limit == timedelta(seconds=30) + HOLD_GRACE


@pytest.mark.parametrize("deliveries", [0, MAX_DELIVERIES + 1])
def test_a_task_gets_one_to_five_deliveries(deliveries: int) -> None:
    with pytest.raises(ValueError, match="число выдач"):
        RetryPolicy(max_deliveries=deliveries, retry_on=(ConnectionError,))


def test_a_retry_names_the_failures_it_is_for_and_only_a_retry_does() -> None:
    with pytest.raises(ValueError, match="повтор"):
        RetryPolicy(max_deliveries=3)
    with pytest.raises(ValueError, match="повтор"):
        RetryPolicy(max_deliveries=1, retry_on=(ConnectionError,))


def test_another_delivery_is_earned_by_a_listed_failure_before_the_last_delivery() -> None:
    assert RETRY_TRANSIENT.allows_another(ConnectionError(), delivery=1)
    assert RETRY_TRANSIENT.allows_another(TimeoutError(), delivery=MAX_DELIVERIES - 1)
    assert not RETRY_TRANSIENT.allows_another(TimeoutError(), delivery=MAX_DELIVERIES)
    assert not RETRY_TRANSIENT.allows_another(ValueError(), delivery=1)
    assert not NO_RETRY.allows_another(ConnectionError(), delivery=1)


def test_a_tick_is_never_retried() -> None:
    with pytest.raises(ValueError, match="такт"):
        declare("probe.tick", kind=TaskKind.TICK, retry=RETRY_TRANSIENT)
    assert declare("probe.tick", kind=TaskKind.TICK).kind is TaskKind.TICK


def test_a_declaration_is_typed_by_its_payload() -> None:
    task = TaskDeclaration(
        name="probe.home",
        queue=TaskQueue.CRITICAL,
        payload=HomeProbe,
        deadline=timedelta(seconds=1),
        retry=NO_RETRY,
    )

    assert task.payload is HomeProbe
    assert task.kind is TaskKind.WORK


def test_a_payload_is_frozen_and_ignores_fields_it_does_not_know() -> None:
    payload = Probe.model_validate({"note": "старый потребитель", "added_later": 1})

    assert payload.note == "старый потребитель"
    with pytest.raises(ValidationError):
        payload.__setattr__("note", "другое")


def test_a_home_payload_gives_the_scope_and_the_log_fields() -> None:
    payload = HomeProbe(home=Home.RU, user_id=USER_ID, org_id=ORG_ID, record_id=RECORD_ID)
    platform = HomeProbe(home=Home.EU, record_id=RECORD_ID)

    assert payload.scope() == TenancyScope(Home.RU, USER_ID, ORG_ID)
    assert payload.log_fields() == {"home": Home.RU, "user_id": USER_ID, "org_id": ORG_ID}
    assert platform.scope() == TenancyScope(Home.EU)
    assert platform.log_fields() == {"home": Home.EU}
    assert Probe(note="x").log_fields() == {}


def test_a_task_secret_travels_in_clear_and_is_masked_for_diagnosis() -> None:
    payload = Probe(note="сброс", link=SecretStr("https://whisperer.one/reset?t=abc"))

    sent = payload.model_dump(mode="json")
    kept = payload.model_dump(mode="json", context={MASK_SECRETS: True})

    assert sent["link"] == "https://whisperer.one/reset?t=abc"
    assert kept["link"] == "***"
    assert Probe.model_validate(sent).link == SecretStr("https://whisperer.one/reset?t=abc")
    assert "abc" not in repr(payload)

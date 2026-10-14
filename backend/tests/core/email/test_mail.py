"""Mail is written with its cause, sent once, retried on 4xx, refused on 5xx, purged."""

from datetime import timedelta
from email.message import EmailMessage

import pytest
import sqlalchemy as sa

from shosai.core.email.delivery import MAX_ATTEMPTS, pause_after
from shosai.core.email.messages import EmailKind, OutgoingEmail
from shosai.core.email.records import EmailMessage as MailRow
from shosai.core.email.records import EmailSuppression
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from tests.core.email.bench import (
    ACCOUNT_MAILBOX,
    NOTIFICATIONS_MAILBOX,
    USER_ID,
    MailBench,
    mail_bench,
)
from tests.doubles.smtp import captured_email
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

EU = TenancyScope(Home.EU, USER_ID)
CODE = OutgoingEmail(
    recipient="person@example.org", kind=EmailKind.ACCOUNT, template="probe.code", locale="ru",
    params={"name": "Анна"}, secrets={"code": "482 913"}, user_id=USER_ID,
)  # fmt: skip


class RolledBackError(Exception):
    """The caller's effect failed after the mail was put in its transaction."""


async def rows(run_slot: RunSlot) -> list[dict[str, object]]:
    """The mail rows of the EU home."""
    found = await fetch_rows(
        run_slot.claimed.connections[Home.EU],
        "SELECT id, kind, status, attempts, smtp_code, secrets, "
        "run_at BETWEEN now() + interval '25 seconds' AND now() + interval '30 seconds' AS paused "
        "FROM email_messages ORDER BY created_at",
    )
    return [dict(row) for row in found]


async def sweep_and_send(bench: MailBench) -> int:
    """One sweep of the EU home and every send it queued, done in this process."""
    claimed = await bench.delivery.claim(Home.EU)
    for message_id, _kind in claimed:
        await bench.delivery.send(Home.EU, message_id)
    return len(claimed)


async def enqueue_and_fail(bench: MailBench, homes: DatabaseAccess) -> None:
    """Write a mail, then fail the caller's effect in the same transaction."""
    async with homes.transactions.begin(EU) as session:
        await bench.port.enqueue(session, CODE)
        raise RolledBackError


async def test_a_rolled_back_transaction_sends_nothing(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    with captured_email() as captured:
        bench = mail_bench(homes.transactions, captured.port)
        with pytest.raises(RolledBackError):
            await enqueue_and_fail(bench, homes)
        sent = await sweep_and_send(bench)

    assert sent == 0
    assert captured.messages == []
    assert await rows(run_slot) == []


async def test_a_committed_mail_is_delivered_once_from_its_mailbox(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    with captured_email() as captured:
        bench = mail_bench(homes.transactions, captured.port)
        async with homes.transactions.begin(EU) as session:
            mail_id = await bench.port.enqueue(session, CODE)
        assert mail_id is not None
        await sweep_and_send(bench)
        # Задача, поставленная второй раз, письмо уже отправленным не шлёт.
        await bench.delivery.send(Home.EU, mail_id)

    [(sender, message)] = captured.received
    [row] = await rows(run_slot)
    assert sender == ACCOUNT_MAILBOX
    assert message["From"] == f"Shosai <{ACCOUNT_MAILBOX}>"
    assert message["Subject"] == "Ваш код 482 913"
    assert message["Message-ID"] == f"<{mail_id.hex}@shosai.example>"
    assert message["Auto-Submitted"] == "auto-generated"
    assert message["List-Unsubscribe"] is None
    assert "482 913" in plain_text(message)
    assert (row["status"], row["attempts"], row["smtp_code"], row["secrets"]) == (
        "sent",
        1,
        250,
        None,
    )


def plain_text(message: EmailMessage) -> str:
    """The plain-text part of a message."""
    part = message.get_body(preferencelist=("plain",))
    assert part is not None
    return str(part.get_content())


async def test_a_secret_is_encrypted_in_the_row(homes: DatabaseAccess, run_slot: RunSlot) -> None:
    bench = mail_bench(homes.transactions, 1)
    async with homes.transactions.begin(EU) as session:
        await bench.port.enqueue(session, CODE)

    [row] = await rows(run_slot)
    sealed = row["secrets"]
    assert isinstance(sealed, bytes)
    assert b"482" not in sealed
    assert bench.key_ring.decrypt(sealed) == '{"code": "482 913"}'


@pytest.mark.parametrize(
    ("answer", "outcome"),
    [
        ("451 4.3.0 Try again later", ("queued", 451, True)),
        ("550 5.1.1 No such mailbox", ("failed", 550, False)),
    ],
)
async def test_a_4xx_answer_is_tried_again_and_a_5xx_one_is_final(
    homes: DatabaseAccess, run_slot: RunSlot, answer: str, outcome: tuple[str, int, bool]
) -> None:
    with captured_email() as captured:
        captured.answers.append(answer)
        bench = mail_bench(homes.transactions, captured.port)
        async with homes.transactions.begin(EU) as session:
            await bench.port.enqueue(session, CODE)
        await sweep_and_send(bench)

    [row] = await rows(run_slot)
    assert captured.messages == []
    assert (row["status"], row["smtp_code"], row["paused"]) == outcome
    assert bench.sample("account", "deferred" if outcome[2] else "failed") == 1


async def test_a_suppressed_newsletter_is_skipped_and_account_mail_still_goes(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = mail_bench(homes.transactions, 1)
    news = OutgoingEmail(
        recipient="person@example.org", kind=EmailKind.NEWSLETTER, template="core.mail_check",
        locale="en", params={"sample_code": "1", "url": "https://shosai.example"}, user_id=USER_ID,
    )  # fmt: skip
    async with homes.transactions.begin(EU) as session:
        await session.execute(
            sa.insert(EmailSuppression).values(user_id=USER_ID, kind="newsletter", source="link")
        )
        skipped = await bench.port.enqueue(session, news)
        written = await bench.port.enqueue(session, CODE)

    assert skipped is None
    assert written is not None
    assert [row["kind"] for row in await rows(run_slot)] == ["account"]
    assert bench.sample("newsletter", "suppressed") == 1


async def test_a_repeated_campaign_writes_one_mail(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = mail_bench(homes.transactions, 1)
    news = OutgoingEmail(
        recipient="person@example.org", kind=EmailKind.NEWSLETTER, template="core.mail_check",
        locale="en", params={"sample_code": "1", "url": "https://shosai.example"},
        user_id=USER_ID, campaign_key="news-2026-10",
    )  # fmt: skip

    for _ in range(2):
        async with homes.transactions.begin(EU) as session:
            await bench.port.enqueue(session, news)

    assert len(await rows(run_slot)) == 1
    assert bench.sample("newsletter", "repeated") == 1


async def test_a_newsletter_carries_one_click_unsubscribe_and_leaves_the_notification_box(
    homes: DatabaseAccess,
) -> None:
    news = OutgoingEmail(
        recipient="person@example.org", kind=EmailKind.NEWSLETTER, template="core.mail_check",
        locale="ar", params={"sample_code": "1", "url": "https://shosai.example"},
        user_id=USER_ID,
    )  # fmt: skip
    with captured_email() as captured:
        bench = mail_bench(homes.transactions, captured.port)
        async with homes.transactions.begin(EU) as session:
            await bench.port.enqueue(session, news)
        await sweep_and_send(bench)

    [(sender, message)] = captured.received
    html = message.get_body(preferencelist=("html",))
    assert html is not None
    assert sender == NOTIFICATIONS_MAILBOX
    assert message["List-Unsubscribe"].startswith(
        "<https://shosai.example/v1/unsubscribe?t=v2.eu.newsletter."
    )
    assert message["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert 'dir="rtl"' in str(html.get_content())


async def test_a_lapsed_sending_lease_is_sent_again_and_a_live_one_is_not(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    with captured_email() as captured:
        bench = mail_bench(homes.transactions, captured.port)
        async with homes.transactions.begin(EU) as session:
            mail_id = await bench.port.enqueue(session, CODE)
            # Отправитель взял письмо и умер: аренда ещё жива — второй не берёт.
            await session.execute(
                sa.update(MailRow).where(MailRow.id == mail_id)
                .values(status="sending", sending_until=sa.func.now() + timedelta(minutes=5))
            )  # fmt: skip
        assert mail_id is not None
        await bench.delivery.send(Home.EU, mail_id)
        held = len(captured.messages)
        async with homes.transactions.begin(EU) as session:
            await session.execute(
                sa.update(MailRow).where(MailRow.id == mail_id)
                .values(sending_until=sa.func.now() - timedelta(seconds=1),
                        run_at=sa.func.now() - timedelta(seconds=1))
            )  # fmt: skip
        sent_again = await sweep_and_send(bench)

    assert (held, sent_again, len(captured.messages)) == (0, 1, 1)


async def test_mail_finished_a_week_ago_is_purged(homes: DatabaseAccess, run_slot: RunSlot) -> None:
    bench = mail_bench(homes.transactions, 1)
    async with homes.transactions.begin(EU) as session:
        old = await bench.port.enqueue(session, CODE)
        await bench.port.enqueue(session, CODE)
        await session.execute(
            sa.update(MailRow).where(MailRow.id == old)
            .values(status="sent", finished_at=sa.func.now() - timedelta(days=8))
        )  # fmt: skip

    removed = await bench.delivery.purge(Home.EU)

    assert removed == 1
    assert [row["status"] for row in await rows(run_slot)] == ["queued"]


async def test_the_eighth_deferral_is_final(homes: DatabaseAccess, run_slot: RunSlot) -> None:
    with captured_email() as captured:
        captured.answers.append("421 4.7.0 Too many connections")
        bench = mail_bench(homes.transactions, captured.port)
        async with homes.transactions.begin(EU) as session:
            mail_id = await bench.port.enqueue(session, CODE)
            await session.execute(
                sa.update(MailRow).where(MailRow.id == mail_id).values(attempts=MAX_ATTEMPTS - 1)
            )
        await sweep_and_send(bench)

    [row] = await rows(run_slot)
    assert (row["status"], row["attempts"], row["smtp_code"]) == ("failed", MAX_ATTEMPTS, 421)


def test_the_pause_doubles_from_30_seconds_up_to_an_hour() -> None:
    pauses = [pause_after(attempts).total_seconds() for attempts in range(1, MAX_ATTEMPTS + 2)]

    assert pauses == [30, 60, 120, 240, 480, 960, 1920, 3600, 3600]

"""`shosai email check`: the operator proves the mail path from both mailboxes (F6-C11)."""

from pathlib import Path

from shosai.core.kernel.homes import Home
from tests.composition.role_process import run_command
from tests.doubles.smtp import captured_email
from tests.harness.connections import fetch_rows
from tests.harness.process_environ import slot_environ
from tests.harness.run_slot import RunSlot
from tests.harness.settings import HarnessSettings

ACCEPTED = "Проверочное письмо принято сервером"


async def test_the_check_sends_one_mail_of_each_kind_without_the_database(
    run_slot: RunSlot, harness_settings: HarnessSettings, tmp_path: Path
) -> None:
    with captured_email() as captured:
        environ = slot_environ(run_slot, harness_settings) | {
            "SMTP_PORT": str(captured.port),
            "SMTP_ACCOUNT_USER": "account@shosai.example",
            "SMTP_NOTIFICATIONS_USER": "info@shosai.example",
        }
        code, lines = await run_command(
            ["email", "check", "--to", "owner@example.org", "--locale", "ja"],
            environ,
            tmp_path / "check.log",
        )

    senders = [sender for sender, _ in captured.received]
    rows = await fetch_rows(
        run_slot.claimed.connections[Home.EU], "SELECT count(*) AS n FROM email_messages"
    )
    assert code == 0
    assert senders == ["account@shosai.example", "info@shosai.example", "info@shosai.example"]
    assert all(message["Subject"] == "Shosai メール確認" for message in captured.messages)
    assert [line["kind"] for line in lines if line["message"] == ACCEPTED] == [
        "account",
        "notification",
        "newsletter",
    ]
    assert rows == [{"n": 0}]


async def test_a_refused_check_fails_the_command(
    run_slot: RunSlot, harness_settings: HarnessSettings, tmp_path: Path
) -> None:
    with captured_email() as captured:
        captured.answers.extend(["550 5.7.1 Sender not allowed"] * 3)
        environ = slot_environ(run_slot, harness_settings) | {"SMTP_PORT": str(captured.port)}
        code, lines = await run_command(
            ["email", "check", "--to", "owner@example.org"], environ, tmp_path / "check.log"
        )

    refused = [line for line in lines if line["message"] == "Проверочное письмо не принято"]
    assert code == 1
    assert [line["code"] for line in refused] == [550, 550, 550]

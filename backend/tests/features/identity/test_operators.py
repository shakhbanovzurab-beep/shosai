"""Operator roles, the owner's routes and the EU audit log (identity step 8a, SM-12)."""

from datetime import UTC, datetime

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from shosai.core.events.subscriptions import ReceivedEvent
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.entrypoints.cli import build_parser
from shosai.features.identity.channels.subscriptions import audit_operator_action
from shosai.features.identity.contracts import OperatorActed, OperatorAction, OperatorRole
from shosai.features.identity.domain.directory import email_hmac
from shosai.features.identity.domain.emails import normalize_email
from tests.composition.public_routes import route_snapshot
from tests.features.identity.registration_bench import (
    DIRECTORY_KEY,
    RegistrationBench,
    registration_bench,
)
from tests.features.identity.test_deletion import events
from tests.features.identity.test_profile import bearer
from tests.features.identity.test_sign_in import EMAIL, account, login
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

OTHER_EMAIL = "support.person@example.com"


async def owner(bench: RegistrationBench) -> None:
    """The first owner, as `shosai identity grant-operator` gives it."""
    address = email_hmac(DIRECTORY_KEY, normalize_email(EMAIL))
    await bench.operators.grant(address, OperatorRole.OWNER)


async def test_every_admin_route_refuses_a_person_without_the_role(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        await account(bench, run_slot)
        headers = bearer((await login(bench))["access_token"])
        admin = [
            (method, path.replace("{user_id}", str(new_id())))
            for method, _, path in (key.partition(" ") for key in route_snapshot(bench.app))
            if path.startswith("/v1/admin/")
        ]
        answers = {
            (method, path): (await bench.http.request(method, path, headers=headers, json={}))
            for method, path in admin
        }

    assert len(admin) >= 3
    assert {key: answer.status_code for key, answer in answers.items()} == dict.fromkeys(
        answers, 403
    )
    assert {answer.json()["error"]["code"] for answer in answers.values()} == {
        "operator_role_required"
    }


async def test_an_owner_gives_roles_and_the_last_owner_keeps_the_role(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis, redis_cache: Redis
) -> None:
    async with registration_bench(homes.transactions, valkey, redis_cache) as bench:
        other = await account(bench, run_slot, email=OTHER_EMAIL)
        me = await account(bench, run_slot)
        await owner(bench)
        headers = bearer((await login(bench))["access_token"])
        given = await bench.http.put(
            f"/v1/admin/operators/{other}", headers=headers, json={"roles": ["support"]}
        )
        listed = (await bench.http.get("/v1/admin/operators", headers=headers)).json()
        profile = (await bench.http.get("/v1/me", headers=headers)).json()
        native = (await bench.http.get("/v1/auth/me", headers=headers)).json()
        demoted = await bench.http.put(
            f"/v1/admin/operators/{me}", headers=headers, json={"roles": ["support"]}
        )
        removed = await bench.http.delete(f"/v1/admin/operators/{me}", headers=headers)
        taken = await bench.http.delete(f"/v1/admin/operators/{other}", headers=headers)

    assert given.json()["roles"] == ["support"]
    assert {(item["user_id"], tuple(item["roles"])) for item in listed["items"]} == {
        (str(me), ("owner",)), (str(other), ("support",)),
    }  # fmt: skip
    assert (profile["operator_roles"], native["role"]) == (["owner"], "admin")
    assert [answer.status_code for answer in (demoted, removed)] == [409, 409]
    assert {answer.json()["error"]["code"] for answer in (demoted, removed)} == {"last_owner"}
    assert taken.status_code == 204
    actions = [name for name in await events(run_slot) if name == "identity.operator.acted"]
    assert len(actions) == 3


async def test_an_action_leaves_one_audit_row_that_the_application_cannot_change(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    target = new_id()
    event = OperatorActed(
        operator_id=new_id(), target_user_id=target, target_home=Home.RU,
        action=OperatorAction.ROLES_CHANGED,
    )  # fmt: skip
    received = ReceivedEvent(event, new_id(), 1, datetime.now(UTC), TenancyScope(Home.RU, target))
    eu = TenancyScope(Home.EU)
    for _ in range(2):
        async with homes.transactions.begin(eu) as session:
            await audit_operator_action(session, received)

    rows = await fetch_rows(
        run_slot.claimed.connections[Home.EU], "SELECT action FROM operator_audit_events"
    )
    assert rows == [{"action": "operator_roles_changed"}]
    for statement in (
        "UPDATE operator_audit_events SET reason_code = 'changed'",
        "DELETE FROM operator_audit_events",
    ):
        with pytest.raises(ProgrammingError, match="permission denied"):
            async with homes.transactions.begin(eu) as session:
                await session.execute(text(statement))


def test_the_first_owner_is_given_from_the_command_line() -> None:
    arguments = build_parser().parse_args(
        ["identity", "grant-operator", "--email", "owner@example.com", "--role", "owner"]
    )

    assert (arguments.role, arguments.tool, arguments.operator_role) == (
        "identity", "grant-operator", "owner",
    )  # fmt: skip

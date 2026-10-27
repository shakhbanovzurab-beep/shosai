"""Studio's tables: a person's own rows only, prompts kept with their person and role, the
platform's history never rewritten, and a person's part of export, transfer and erasure."""

import json
import uuid
from collections.abc import Mapping
from decimal import Decimal

import pytest
from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import DBAPIError

from shosai.core.account_data.handlers import AccountRef
from shosai.core.db.model_base import ModelBase
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.studio.application.account_data import StudioAccountData
from shosai.features.studio.infrastructure.person_records import (
    ContextRecord,
    PromptRecord,
    PromptSkillRecord,
    RoleModelRecord,
    RolePromptRecord,
)
from shosai.features.studio.infrastructure.platform_records import (
    CatalogueRecord,
    PlatformVersionRecord,
    RoleDefaultRecord,
)
from tests.harness.database_access import DatabaseAccess


def prompt(person: uuid.UUID, **fields: object) -> dict[str, object]:
    """A prompt's columns: the code role by default."""
    return {
        "id": uuid.uuid4(), "user_id": person, "name": "Interview", "role": "code",
        "content": "Explain the complexity.",
    } | fields  # fmt: skip


def linked_skill(person: uuid.UUID, prompt_id: object) -> dict[str, object]:
    """A skill's link to a prompt, first in its order."""
    return {
        "id": uuid.uuid4(), "user_id": person, "prompt_id": prompt_id,
        "skill_id": uuid.uuid4(), "position": 0,
    }  # fmt: skip


def settings_row(person: uuid.UUID, **fields: object) -> dict[str, object]:
    """A person's model settings of the code role."""
    return {
        "user_id": person, "role": "code", "model_id": None,
        "temperature": Decimal("0.7"), "max_tokens": 4096, "reasoning": False,
    } | fields  # fmt: skip


def catalogue_row(model_id: str) -> dict[str, object]:
    """A standard text model's columns."""
    return {
        "id": model_id, "openrouter_id": f"maker/{model_id}", "name": model_id, "maker": "Maker",
        "context_length": 1000, "max_output_tokens": 1000, "capabilities": ["text"],
        "supports_temperature": True, "supports_reasoning": False, "tier": "standard",
    }  # fmt: skip


async def write(
    homes: DatabaseAccess,
    scope: TenancyScope,
    model: type[ModelBase],
    rows: list[dict[str, object]],
) -> None:
    """Insert rows in one transaction of the scope."""
    async with homes.transactions.begin(scope) as session:
        await session.execute(insert(model), rows)


async def test_a_person_reads_and_writes_only_their_own_rows(homes: DatabaseAccess) -> None:
    person, other = uuid.uuid4(), uuid.uuid4()
    mine = TenancyScope(Home.RU, person)
    await write(homes, mine, ContextRecord, [{"user_id": person, "content": "I lead product."}])
    await write(homes, mine, PromptRecord, [prompt(person)])
    async with homes.transactions.begin(TenancyScope(Home.RU, other), read_only=True) as session:
        seen = [
            (await session.scalars(select(model.user_id))).all()
            for model in (ContextRecord, PromptRecord)
        ]

    assert seen == [[], []]
    with pytest.raises(DBAPIError, match="row-level security"):
        await write(homes, TenancyScope(Home.RU, other), PromptRecord, [prompt(person)])


@pytest.mark.parametrize(
    ("model", "fields", "rule"),
    [
        (PromptRecord, {"role": "transcript"}, "role_known"),
        (PromptRecord, {"name": ""}, "name_length"),
        (PromptRecord, {"content": "c" * 20_001}, "content_length"),
        (ContextRecord, {"content": "я" * 4_001}, "content_length"),
        (RoleModelRecord, {"max_tokens": 100}, "max_tokens_range"),
        (RoleModelRecord, {"temperature": Decimal("2.5")}, "temperature_range"),
    ],
)
async def test_the_database_keeps_each_rule(
    homes: DatabaseAccess, model: type[ModelBase], fields: Mapping[str, object], rule: str
) -> None:
    person = uuid.uuid4()
    base: dict[str, object] = {
        PromptRecord: prompt(person),
        ContextRecord: {"user_id": person, "content": ""},
        RoleModelRecord: settings_row(person),
    }[model]

    with pytest.raises(DBAPIError, match=rule):
        await write(homes, TenancyScope(Home.RU, person), model, [{**base, **fields}])


async def test_an_active_prompt_keeps_its_role_and_goes_with_its_prompt(
    homes: DatabaseAccess,
) -> None:
    person = uuid.uuid4()
    scope = TenancyScope(Home.RU, person)
    row = prompt(person)
    await write(homes, scope, PromptRecord, [row])
    pointer = {"user_id": person, "role": "code", "prompt_id": row["id"]}
    skill = linked_skill(person, row["id"])
    await write(homes, scope, RolePromptRecord, [pointer])
    await write(homes, scope, PromptSkillRecord, [skill])

    with pytest.raises(DBAPIError, match="fk_role_prompts"):
        await write(homes, scope, RolePromptRecord, [{**pointer, "role": "notes"}])
    with pytest.raises(DBAPIError, match="fk_role_prompts"):
        async with homes.transactions.begin(scope) as session:
            await session.execute(update(PromptRecord).values(role="notes"))
    async with homes.transactions.begin(scope) as session:
        await session.execute(delete(PromptRecord))
        left = [
            (await session.scalars(select(model.user_id))).all()
            for model in (RolePromptRecord, PromptSkillRecord)
        ]

    assert left == [[], []]


async def test_the_platform_tables_live_in_the_eu_home_and_keep_their_history(
    homes: DatabaseAccess,
) -> None:
    eu = TenancyScope(Home.EU)
    await write(homes, eu, CatalogueRecord, [catalogue_row("a"), catalogue_row("b")])
    await write(homes, eu, RoleDefaultRecord, [{"role": "leo", "model_id": "a"}])
    version = {"id": uuid.uuid4(), "number": 1, "config": {}, "comment": "First."}
    await write(homes, eu, PlatformVersionRecord, [version])

    for statement in (
        delete(CatalogueRecord),
        delete(RoleDefaultRecord),
        update(PlatformVersionRecord).values(comment="Rewritten."),
        delete(PlatformVersionRecord),
    ):
        with pytest.raises(DBAPIError, match="permission denied"):
            async with homes.transactions.begin(eu) as session:
                await session.execute(statement)
    with pytest.raises(DBAPIError, match="fallback_differs"):
        async with homes.transactions.begin(eu) as session:
            await session.execute(update(RoleDefaultRecord).values(fallback_model_id="a"))
    with pytest.raises(DBAPIError, match="does not exist"):
        async with homes.transactions.begin(TenancyScope(Home.RU), read_only=True) as session:
            await session.execute(select(CatalogueRecord.id))


async def test_export_transfer_and_erasure_cover_every_row(homes: DatabaseAccess) -> None:
    person = uuid.uuid4()
    scope = TenancyScope(Home.RU, person)
    row = prompt(person)
    await write(homes, scope, ContextRecord, [{"user_id": person, "content": "I lead product."}])
    await write(homes, scope, PromptRecord, [row])
    pointer = {"user_id": person, "role": "code", "prompt_id": row["id"]}
    await write(homes, scope, PromptSkillRecord, [linked_skill(person, row["id"])])
    await write(homes, scope, RolePromptRecord, [pointer])
    await write(homes, scope, RoleModelRecord, [settings_row(person, model_id="a")])
    handler = StudioAccountData(homes.transactions)
    russian, european = AccountRef(person, Home.RU), AccountRef(person, Home.EU)

    exported = {
        item.name: b"".join([chunk async for chunk in item.chunks])
        async for item in handler.export(russian)
    }
    await handler.copy(russian, Home.EU)
    await handler.copy(russian, Home.EU)
    same = await handler.manifest(russian) == await handler.manifest(european)
    await handler.erase(russian)
    await handler.erase(russian)
    await handler.purge(european)

    assert set(exported) == {
        "user_contexts.jsonl", "prompt_templates.jsonl", "prompt_skills.jsonl",
        "role_prompts.jsonl", "model_role_assignments.jsonl",
    }  # fmt: skip
    prompts = [json.loads(line) for line in exported["prompt_templates.jsonl"].splitlines()]
    assert [item["name"] for item in prompts] == ["Interview"]
    assert same
    assert await handler.remains(russian) == ()
    assert await handler.remains(european) == ()

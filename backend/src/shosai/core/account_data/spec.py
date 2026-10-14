"""Declarations of a person's data, per owner (ADR 0045 point 7).

Each slice declares, on its `FeatureModule`, every table that holds rows of a person,
every object-storage prefix keyed by a person and every external grant made in their
name, with what happens to each when the account is erased. Core declares its own tables
here too, because core cannot import a slice. `identity` runs export, erasure and
transfer over these declarations; a metadata test fails when a table with a person's id
is declared by nobody, or by two owners.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

OWNER_NAME: Final = re.compile(r"[a-z][a-z0-9_]*")


class Treatment(StrEnum):
    """What erasing an account does to a table's rows of that person."""

    # Строки человека экспортируются и стираются обработчиком владельца.
    ERASE = "erase"
    # Строки остаются по закону (402-ФЗ, 5 лет), аккаунт обезличивается.
    KEEP_BY_LAW = "keep_by_law"
    # Только идентификаторы, удаляются собственным сроком хранения таблицы.
    EXPIRES = "expires"


@dataclass(frozen=True, slots=True)
class TableCoverage:
    """One table and its treatment."""

    table: str
    treatment: Treatment


@dataclass(frozen=True, slots=True)
class AccountDataSpec:
    """What one owner holds of a person."""

    # Владелец: имя среза или «core».
    owner: str
    tables: tuple[TableCoverage, ...] = ()
    # Префиксы ключей в бакете дома; ключ продолжается идентификатором человека.
    prefixes: tuple[str, ...] = ()
    # Внешние гранты от имени человека (Nango, OAuth): отзываются при стирании.
    external_grants: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not OWNER_NAME.fullmatch(self.owner):
            message = f"владелец данных {self.owner!r} — имя среза в snake_case"
            raise ValueError(message)
        names = [coverage.table for coverage in self.tables]
        if len(names) != len(set(names)):
            message = f"владелец {self.owner}: таблица объявлена дважды"
            raise ValueError(message)


# Таблицы ядра со строками человека. Обработчики стирания и экспорта — шаг 7 плана identity.
CORE_ACCOUNT_DATA: Final = AccountDataSpec(
    owner="core",
    tables=(
        # Письма содержат адрес получателя и параметры текста.
        TableCoverage("email_messages", Treatment.ERASE),
        TableCoverage("email_suppressions", Treatment.ERASE),
        TableCoverage("provider_costs", Treatment.KEEP_BY_LAW),
        # Ключи эффектов живут не дольше 90 дней, события outbox — 7 дней; в них только id.
        TableCoverage("effect_keys", Treatment.EXPIRES),
        TableCoverage("outbox_messages", Treatment.EXPIRES),
    ),
)

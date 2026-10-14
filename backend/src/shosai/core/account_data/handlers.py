"""Exporting and erasing a person's data owner by owner: the handlers identity runs.

An owner whose declaration erases something — a table with `ERASE`, an object prefix, an
external grant — binds one handler to `ACCOUNT_DATA_HANDLERS`, and composition refuses to
start when such an owner has no handler or two, or a handler has no declaration (ADR 0045
point 7). Erasure is idempotent: the saga runs it again after a failure, and a run that
finds nothing left succeeds. Export yields the owner's files of the archive, one after
another; the runner writes each into the ZIP before asking for the next. A handler opens
its own short transactions in the account's home and calls storage outside them (§14
rule 1).
"""

from collections import Counter
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Final, Protocol
from uuid import UUID

from shosai.core.account_data.spec import AccountDataSpec, Treatment
from shosai.core.kernel.homes import Home
from shosai.core.ports.keys import Cardinality, PortKey


@dataclass(frozen=True, slots=True)
class AccountRef:
    """The account whose data is exported or erased, and the home it lives in."""

    user_id: UUID
    home: Home


@dataclass(frozen=True, slots=True)
class ExportFile:
    """One file of the export archive: its name in the owner's folder and its bytes."""

    # Имя таблицы с `.jsonl` или путь объекта; папка владельца добавляется при записи.
    name: str
    chunks: AsyncIterator[bytes]


class AccountDataHandler(Protocol):
    """Exports and erases what one owner holds of a person."""

    @property
    def owner(self) -> str:
        """The owner of the declaration this handler serves: a slice's name or `core`."""
        ...

    def export(self, account: AccountRef) -> AsyncIterator[ExportFile]:
        """The owner's files of the account: one JSON Lines file per table, then objects."""
        ...

    async def erase(self, account: AccountRef) -> None:
        """Erase the owner's rows, objects and grants of the account; a repeat changes nothing."""
        ...


ACCOUNT_DATA_HANDLERS: Final = PortKey[AccountDataHandler](
    "core.account_data_handlers", Cardinality.MANY
)


def needs_handler(spec: AccountDataSpec) -> bool:
    """Whether erasing an account touches anything of this owner."""
    erases_rows = any(coverage.treatment is Treatment.ERASE for coverage in spec.tables)
    return erases_rows or bool(spec.prefixes) or bool(spec.external_grants)


def handler_problems(
    specs: Sequence[AccountDataSpec], handlers: Sequence[AccountDataHandler]
) -> list[str]:
    """Every owner that erases without exactly one handler, and every handler without one."""
    declared = {spec.owner for spec in specs}
    bound = Counter(handler.owner for handler in handlers)
    problems = [
        f"{spec.owner}: стирает данные человека, но обработчиков {bound[spec.owner]}, а не один"
        for spec in specs
        if needs_handler(spec) and bound[spec.owner] != 1
    ]
    problems += [
        f"{owner}: обработчик стирания без объявления в реестре"
        for owner in sorted(bound)
        if owner not in declared
    ]
    return sorted(problems)

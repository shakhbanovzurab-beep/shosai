"""Slot lifecycle of one run: claim, return to the prepared state, reference, final check."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from tests.harness.catalog import CatalogFingerprint, restore_prepared_state
from tests.harness.settings import HarnessSettings
from tests.harness.slots import ClaimedSlot, claim_slot
from whisperer.core.kernel.homes import Home


@dataclass(frozen=True, slots=True)
class RunSlot:
    """The run's slot with each home's catalog reference and what the claim restored."""

    claimed: ClaimedSlot
    references: Mapping[Home, CatalogFingerprint]
    restored: Mapping[Home, list[str]]

    async def catalog_changes(self) -> list[str]:
        """Differences from the reference per home; an empty list means the schema is intact."""
        changes: list[str] = []
        for home, connection in self.claimed.connections.items():
            current = await CatalogFingerprint.take(connection)
            changes.extend(
                f"{home}: {change}" for change in current.changes_since(self.references[home])
            )
        return changes

    def summary(self) -> list[str]:
        """Lines for the pytest summary: the slot number and what a crashed run had left."""
        lines = [f"слот тестовых баз: whisperer_test_{self.claimed.number} во всех домах"]
        lines.extend(
            f"восстановлено после упавшего прогона, {home}: {change}"
            for home, changes in self.restored.items()
            for change in changes
        )
        return lines


async def open_run_slot(settings: HarnessSettings, numbers: Iterable[int]) -> RunSlot:
    """Claim a slot, return it to the prepared state and take each home's reference."""
    return await prepare_run_slot(await claim_slot(settings, numbers))


async def prepare_run_slot(claimed: ClaimedSlot) -> RunSlot:
    """Return a claimed slot to the prepared state and take each home's catalog reference."""
    try:
        restored: dict[Home, list[str]] = {}
        references: dict[Home, CatalogFingerprint] = {}
        for home, connection in claimed.connections.items():
            application_role = claimed.settings.homes[home].application.user
            restored[home] = await restore_prepared_state(connection, application_role)
            references[home] = await CatalogFingerprint.take(connection)
    except BaseException:
        await claimed.release()
        raise
    return RunSlot(claimed=claimed, references=references, restored=restored)

"""The slices of the backend, listed explicitly: nothing is found by importing modules.

A new slice adds its `FeatureModule` here; every role then builds it, registers its
tasks, routes its events, and the route snapshot and the native-contract gate check its
routes (backend README, "Adding a slice").
"""

from collections.abc import Sequence

from shosai.core.access.shareable import ShareableResource
from shosai.core.account_data.spec import CORE_ACCOUNT_DATA, AccountDataSpec
from shosai.core.agent_tools.events import ActionItemExecuted
from shosai.core.ai.events import UserSpendExceeded
from shosai.core.config.gate import ProductionCheck
from shosai.core.config.sections import SettingsSection
from shosai.core.events.domain_event import DomainEvent
from shosai.core.features import FeatureModule
from shosai.features.agent.module import AGENT
from shosai.features.alerting.module import ALERTING
from shosai.features.billing.module import BILLING
from shosai.features.decisions.module import DECISIONS
from shosai.features.files.module import FILES
from shosai.features.identity.module import IDENTITY
from shosai.features.notes.module import NOTES
from shosai.features.tasks.module import TASKS
from shosai.features.workspaces.module import WORKSPACES

FEATURES: tuple[FeatureModule, ...] = (
    IDENTITY,
    WORKSPACES,
    BILLING,
    FILES,
    NOTES,
    TASKS,
    AGENT,
    DECISIONS,
    ALERTING,
)


def check_features(features: Sequence[FeatureModule]) -> None:
    """Refuse a slice listed twice, or a shareable kind or table declared twice.

    A slice listed twice would register its tasks and routes twice; a resource declared by
    two slices would get two owners of its access rules (§7).
    """
    names = [feature.name for feature in features]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        message = f"срезы перечислены дважды: {', '.join(duplicates)}"
        raise ValueError(message)
    resources = shareable_resources(features)
    for label, values in (
        ("вид", [resource.kind for resource in resources]),
        ("таблица", [resource.table.name for resource in resources]),
    ):
        repeated = sorted({value for value in values if values.count(value) > 1})
        if repeated:
            message = f"разделяемый ресурс объявлен дважды ({label}): {', '.join(repeated)}"
            raise ValueError(message)
    check_parents(resources)


def check_parents(resources: Sequence[ShareableResource]) -> None:
    """Refuse a parent kind no slice declares, or a parent that has a parent of its own.

    The policy opens a row to its parent's readers through one level only, so a chain of
    parents never makes a read path the isolation tests did not cover (ADR 0059).
    """
    by_kind = {resource.kind: resource for resource in resources}
    for resource in resources:
        if resource.parent is None:
            continue
        parent = by_kind.get(resource.parent[0])
        if parent is None or parent.parent is not None:
            message = (
                f"разделяемый ресурс {resource.kind}: родитель {resource.parent[0]} не объявлен "
                "или сам имеет родителя"
            )
            raise ValueError(message)


def shareable_resources(features: Sequence[FeatureModule]) -> list[ShareableResource]:
    """Every table the slices share through the access policy (§7)."""
    return [resource for feature in features for resource in feature.shareable]


# События ядра: их, как и события срезов, знают outbox и каталог подписок.
CORE_EVENTS: tuple[type[DomainEvent], ...] = (UserSpendExceeded, ActionItemExecuted)


def feature_events(features: Sequence[FeatureModule]) -> list[type[DomainEvent]]:
    """Every event class the slices declare."""
    return [event for feature in features for event in feature.events]


def platform_events(features: Sequence[FeatureModule]) -> list[type[DomainEvent]]:
    """Core's events and the slices' ones."""
    return [*CORE_EVENTS, *feature_events(features)]


def feature_checks(features: Sequence[FeatureModule]) -> list[ProductionCheck]:
    """Every production check the slices add to the gate."""
    return [check for feature in features for check in feature.production_checks]


def feature_settings_sections(features: Sequence[FeatureModule]) -> list[type[SettingsSection]]:
    """Every settings section the slices declare, read with core's at start."""
    return [section for feature in features for section in feature.settings]


def account_data_specs(features: Sequence[FeatureModule]) -> list[AccountDataSpec]:
    """What core and every slice hold of a person: the registry identity runs."""
    return [CORE_ACCOUNT_DATA, *(spec for feature in features for spec in feature.account_data)]

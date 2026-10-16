"""The slices of the backend, listed explicitly: nothing is found by importing modules.

A new slice adds its `FeatureModule` here; every role then builds it, registers its
tasks, routes its events, and the route snapshot and the native-contract gate check its
routes (backend README, "Adding a slice").
"""

from collections.abc import Sequence

from shosai.core.account_data.spec import CORE_ACCOUNT_DATA, AccountDataSpec
from shosai.core.ai.events import UserSpendExceeded
from shosai.core.config.gate import ProductionCheck
from shosai.core.config.sections import SettingsSection
from shosai.core.events.domain_event import DomainEvent
from shosai.core.features import FeatureModule
from shosai.features.alerting.module import ALERTING
from shosai.features.identity.module import IDENTITY

FEATURES: tuple[FeatureModule, ...] = (IDENTITY, ALERTING)


def check_features(features: Sequence[FeatureModule]) -> None:
    """Refuse a slice listed twice: its tasks and routes would be registered twice."""
    names = [feature.name for feature in features]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        message = f"срезы перечислены дважды: {', '.join(duplicates)}"
        raise ValueError(message)


# События ядра: их, как и события срезов, знают outbox и каталог подписок.
CORE_EVENTS: tuple[type[DomainEvent], ...] = (UserSpendExceeded,)


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

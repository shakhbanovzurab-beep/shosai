"""The slices of the backend, listed explicitly: nothing is found by importing modules.

A new slice adds its `FeatureModule` here; every role then builds it, registers its
tasks, routes its events, and the route snapshot and the D1 gate check its routes
(backend README, "Adding a slice").
"""

from collections.abc import Sequence

from shosai.core.config.gate import ProductionCheck
from shosai.core.events.domain_event import DomainEvent
from shosai.core.features import FeatureModule

FEATURES: tuple[FeatureModule, ...] = ()


def check_features(features: Sequence[FeatureModule]) -> None:
    """Refuse a slice listed twice: its tasks and routes would be registered twice."""
    names = [feature.name for feature in features]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        message = f"срезы перечислены дважды: {', '.join(duplicates)}"
        raise ValueError(message)


def feature_events(features: Sequence[FeatureModule]) -> list[type[DomainEvent]]:
    """Every event class the slices declare."""
    return [event for feature in features for event in feature.events]


def feature_checks(features: Sequence[FeatureModule]) -> list[ProductionCheck]:
    """Every production check the slices add to the gate."""
    return [check for feature in features for check in feature.production_checks]


def contract_slices(features: Sequence[FeatureModule]) -> frozenset[str]:
    """The D1 slices whose draft routes the composed apps must keep: F1 and every slice."""
    return frozenset({"F1", *(feature.contract_slice for feature in features)})

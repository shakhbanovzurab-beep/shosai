"""Installing the slices' agent tools: what a slice binds is exactly what it declared.

A spec bound without being declared on the slice's `FeatureModule` would reach the model
unseen by the model-facing English test, and a declared spec left unbound would be a tool
the model is offered and cannot call. Either stops the start; then the catalog gets every
tool for the agent.
"""

from collections.abc import Sequence

from shosai.core.agent_tools.catalog import AgentToolCatalog
from shosai.core.features import FeatureModule, FeatureParts


def install_agent_tools(
    features: Sequence[FeatureModule], built: Sequence[FeatureParts], catalog: AgentToolCatalog
) -> None:
    """Check each slice's bound tools against its declared specs, then fill the catalog."""
    for feature, parts in zip(features, built, strict=True):
        declared = {id(spec): spec.name for spec in feature.agent_tools}
        bound = {id(tool.spec): tool.spec.name for tool in parts.agent_tools}
        unseen = sorted(name for key, name in bound.items() if key not in declared)
        unbound = sorted(name for key, name in declared.items() if key not in bound)
        if unseen or unbound:
            message = (
                f"срез {feature.name}: инструменты агента без объявления {unseen}, "
                f"объявленные без обработчиков {unbound}"
            )
            raise ValueError(message)
    catalog.install(tool for parts in built for tool in parts.agent_tools)

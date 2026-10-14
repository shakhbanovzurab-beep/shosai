"""Installing the slices' port bindings, checked against the ports the slices require.

Every slice is built before any binding is installed, so a slice may require a port that a
later slice in `FEATURES` implements. A required port without a binding, or a
single-implementation port bound twice, stops the start (ADR 0045 point 11).
"""

from collections.abc import Sequence

from shosai.core.features import FeatureModule, FeatureParts
from shosai.core.ports.directory import PortDirectory


def install_ports(
    features: Sequence[FeatureModule], built: Sequence[FeatureParts], directory: PortDirectory
) -> None:
    """Install every slice's bindings after checking the requirements of every slice."""
    required = [key for feature in features for key in feature.requires]
    directory.install((binding for parts in built for binding in parts.provides), required)

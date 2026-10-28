"""The published platform layer for the consumers' prompts (`PROMPT_RESOLVER`, ADR 0074).

Read from the process's snapshot: no database read on a prompt's path. Before the first
publish the layer and every addendum are empty, and the consumers' own prompts run alone.
"""

from shosai.features.studio.contracts import PlatformLayer
from shosai.features.studio.domain.platform_layer import PlatformFeature, feature_text, layer_text
from shosai.features.studio.infrastructure.platform_snapshot import PlatformSnapshot


class PlatformPromptReader:
    """The platform part of studio's `PromptResolver`."""

    def __init__(self, snapshot: PlatformSnapshot) -> None:
        self._snapshot = snapshot

    async def platform_layer(self) -> PlatformLayer:
        """The published layer, read from the process's snapshot."""
        published = await self._snapshot.published()
        return PlatformLayer(published.version, layer_text(published.config))

    async def feature_prompt(self, feature: PlatformFeature) -> str:
        """The operator's addendum to a feature's prompt; empty when it is off."""
        return feature_text((await self._snapshot.published()).config, feature)

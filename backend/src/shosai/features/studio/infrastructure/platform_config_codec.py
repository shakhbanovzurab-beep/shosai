"""The platform layer's config as it is stored (JSONB, `schema` 1) and read back.

A stored config names its schema, so a later shape can read an older version: restoring one
re-checks it by today's rules. A section missing from a stored config reads as built-in.
"""

from types import MappingProxyType
from typing import Any

from shosai.features.studio.domain.platform_layer import (
    BUILT_IN,
    SCHEMA,
    FeaturePrompt,
    PlatformConfig,
    PlatformFeature,
    SafetyRule,
)

type ConfigJson = dict[str, Any]


def config_json(config: PlatformConfig) -> ConfigJson:
    """The config as its JSON document."""
    return {
        "schema": SCHEMA,
        "system_prompt": config.system_prompt,
        "safety": {
            "rules": [
                {"id": rule.id, "text": rule.text, "enabled": rule.enabled} for rule in config.rules
            ],
            "blocked_topics": list(config.blocked_topics),
        },
        "features": {
            feature.value: {
                "content": config.features[feature].content,
                "enabled": config.features[feature].enabled,
            }
            for feature in PlatformFeature
            if feature in config.features
        },
    }


def config_of(document: ConfigJson) -> PlatformConfig:
    """The config of a stored document; what it lacks is built-in."""
    safety = document.get("safety") or {}
    stored = document.get("features") or {}
    features = {
        feature: FeaturePrompt(str(item["content"]), enabled=bool(item["enabled"]))
        if (item := stored.get(feature.value))
        else BUILT_IN.features[feature]
        for feature in PlatformFeature
    }
    return PlatformConfig(
        system_prompt=str(document.get("system_prompt", "")),
        rules=tuple(
            SafetyRule(str(rule["id"]), str(rule["text"]), enabled=bool(rule["enabled"]))
            for rule in safety.get("rules", [])
        ),
        blocked_topics=tuple(str(topic) for topic in safety.get("blocked_topics", [])),
        features=MappingProxyType(features),
    )

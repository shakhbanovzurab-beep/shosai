"""The CLAUDE.md "Prompts" gate: all registered model-facing text is English."""

from tests.model_facing.collector import find_violations
from tests.model_facing.registry import MODEL_FACING_SOURCES


def test_every_registered_model_facing_text_is_english() -> None:
    assert find_violations(MODEL_FACING_SOURCES) == []


def test_every_source_is_registered_once() -> None:
    keys = [(source.owner, source.name) for source in MODEL_FACING_SOURCES]

    assert len(keys) == len(set(keys))

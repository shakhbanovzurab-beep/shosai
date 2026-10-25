"""Every write's card has its slice's words in the 16 platform languages (agent step 9b; AG-D1).

A card is rendered from the wording its slice declares beside the write's spec, so no write
may lack one, no preview key in a slice's code may go unworded, and every wording renders in
every language with any value its fields take — a value code by its words, a None by the
field's absence. The cabinet keeps no copy of these words.
"""

import re
from pathlib import Path
from typing import Any, Final

import pytest

from shosai.composition.features import FEATURES
from shosai.core.agent_tools.previews import LANGUAGES, PreviewWording, render_preview
from shosai.core.agent_tools.results import Preview, PreviewParam
from shosai.core.agent_tools.spec import ToolEffect, ToolSpec

SOURCE: Final = Path(__file__).parents[3] / "src" / "shosai" / "features"
# Ключ превью в коде среза: строка `agent.<срез>.<имя>`.
KEY_LITERAL: Final = re.compile(r"""["'](agent\.[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*)["']""")
WRITES: Final[tuple[ToolSpec[Any, Any], ...]] = tuple(
    spec for feature in FEATURES for spec in feature.agent_tools if spec.effect is ToolEffect.WRITE
)
WORDINGS: Final[tuple[PreviewWording, ...]] = tuple(
    wording for spec in WRITES for wording in spec.previews
)


def test_every_write_tool_words_its_cards() -> None:
    unworded = [spec.name for spec in WRITES if not spec.previews]

    assert WRITES
    assert unworded == []


def test_no_preview_key_in_a_slice_goes_unworded() -> None:
    declared = {wording.key for wording in WORDINGS}
    used = {
        key
        for path in SOURCE.glob("*/channels/*.py")
        if path.parent.parent.name != "agent"
        for key in KEY_LITERAL.findall(path.read_text(encoding="utf-8"))
    }

    assert used - declared == set()


@pytest.mark.parametrize("wording", WORDINGS, ids=[wording.key for wording in WORDINGS])
def test_a_card_renders_in_every_language_with_every_value(wording: PreviewWording) -> None:
    coded = {row.param: list(row.values) for row in wording.fields if row.values}
    samples: list[dict[str, PreviewParam]] = [dict.fromkeys(wording.params, "Sample")]
    samples += [{**samples[0], param: value} for param, values in coded.items() for value in values]
    samples.append(dict.fromkeys(wording.params))

    for language in sorted(LANGUAGES):
        for params in samples:
            card = render_preview(wording, Preview(wording.key, params), language)
            assert card.title.strip()
            assert "{" not in card.title
            assert all(label.strip() and value.strip() for label, value in card.fields)

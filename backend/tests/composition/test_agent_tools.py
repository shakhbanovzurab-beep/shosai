"""Composition installs a slice's agent tools only when bound and declared match."""

import pytest

from shosai.composition.agent_tools import install_agent_tools
from shosai.core.agent_tools.catalog import AgentToolCatalog
from shosai.core.features import FeatureModule, FeatureParts
from tests.core.agent_tools.probe_tools import ARCHIVE, ARCHIVE_TOOL, SEARCH, SEARCH_TOOL

NOTES = FeatureModule(name="notes", agent_tools=(SEARCH, ARCHIVE))


def test_declared_and_bound_tools_reach_the_catalog() -> None:
    catalog = AgentToolCatalog()

    install_agent_tools([NOTES], [FeatureParts(agent_tools=(SEARCH_TOOL, ARCHIVE_TOOL))], catalog)

    assert catalog.toolset("notes") == (SEARCH_TOOL, ARCHIVE_TOOL)


@pytest.mark.parametrize(
    ("module", "parts", "named"),
    [
        # Привязан, но не объявлен: модель увидела бы текст, который тест не проверил.
        (
            FeatureModule(name="notes", agent_tools=(SEARCH,)),
            FeatureParts(agent_tools=(SEARCH_TOOL, ARCHIVE_TOOL)),
            "без объявления ['notes.archive']",
        ),
        # Объявлен, но не привязан: модели предложили бы инструмент, который не вызвать.
        (NOTES, FeatureParts(agent_tools=(SEARCH_TOOL,)), "без обработчиков ['notes.archive']"),
    ],
)
def test_a_mismatch_stops_the_start(module: FeatureModule, parts: FeatureParts, named: str) -> None:
    with pytest.raises(ValueError, match=named.replace("[", r"\[").replace("]", r"\]")):
        install_agent_tools([module], [parts], AgentToolCatalog())

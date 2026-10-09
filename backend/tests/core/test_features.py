"""A slice's module names its package and its D1 slice; parts combine in the listed order."""

from datetime import timedelta

import pytest
from fastapi import APIRouter

from shosai.core.features import FeatureModule, FeatureParts, combine_parts
from shosai.core.health.probes import DependencyProbe
from shosai.core.runtime.loops import ScheduledLoop


async def nothing() -> None:
    """Work that does nothing."""


@pytest.mark.parametrize(
    ("name", "contract_slice", "problem"),
    [
        ("Meetings", "S04", "имя среза"),
        ("meetings-v2", "S04", "имя среза"),
        ("meetings", "meetings", "идентификатор в контракте D1"),
        ("meetings", "S", "идентификатор в контракте D1"),
    ],
)
def test_a_module_names_its_package_and_its_slice(
    name: str, contract_slice: str, problem: str
) -> None:
    with pytest.raises(ValueError, match=problem):
        FeatureModule(name=name, contract_slice=contract_slice)


def test_a_module_without_parts_builds_nothing() -> None:
    module = FeatureModule(name="directory", contract_slice="S01")

    assert (module.models, module.events, module.production_checks) == ((), (), ())


def test_parts_combine_in_the_listed_order() -> None:
    first, second = APIRouter(), APIRouter()
    loop = ScheduledLoop("first.sweep", timedelta(seconds=1), nothing)
    probe = DependencyProbe("second.index", nothing, ())

    combined = combine_parts(
        [
            FeatureParts(http_routers=(first,), loops=(loop,)),
            FeatureParts(http_routers=(second,), probes=(probe,)),
        ]
    )

    assert combined.http_routers == (first, second)
    assert (combined.loops, combined.probes) == ((loop,), (probe,))
    assert (combined.ws_routers, combined.task_handlers, combined.subscriptions) == ((), (), ())

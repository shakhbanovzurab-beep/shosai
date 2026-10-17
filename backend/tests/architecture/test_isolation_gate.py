"""Every shareable resource has an isolation test in its slice's tests (§14 rule 12, inv-14).

A slice declares its shareable tables on `FeatureModule.shareable`; for each kind, a test
under `tests/features/<slice>/` must carry `@pytest.mark.isolation(resource="<kind>")`,
the mark of a test that runs the isolation kit over a read path of that resource.
"""

import re
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa

from shosai.composition.features import FEATURES
from shosai.core.access.shareable import ShareableResource
from shosai.core.features import FeatureModule

TESTS = Path(__file__).resolve().parents[1]
MARK = re.compile(r"""pytest\.mark\.isolation\(\s*resource\s*=\s*["']([a-z][a-z0-9_]*)["']\s*\)""")


def missing_isolation_tests(features: Sequence[FeatureModule], tests: Path) -> list[str]:
    """`<slice>: <kind>` for every declared resource without a marked test in its slice."""
    missing: list[str] = []
    for feature in features:
        kinds = {resource.kind for resource in feature.shareable}
        if not kinds:
            continue
        marked: set[str] = set()
        for path in (tests / "features" / feature.name).rglob("*.py"):
            marked |= set(MARK.findall(path.read_text(encoding="utf-8")))
        missing += [f"{feature.name}: {kind}" for kind in sorted(kinds - marked)]
    return missing


def test_every_declared_resource_has_its_isolation_test() -> None:
    assert missing_isolation_tests(FEATURES, TESTS) == []


def fixture_feature() -> FeatureModule:
    table = sa.Table(
        "notes",
        sa.MetaData(),
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("user_id", sa.Uuid),
        sa.Column("org_id", sa.Uuid),
        sa.Column("access", sa.Text),
    )
    return FeatureModule(name="alpha", shareable=(ShareableResource("note", table),))


def test_a_resource_without_a_marked_test_in_its_slice_fails_the_gate(tmp_path: Path) -> None:
    other = tmp_path / "features" / "beta"
    other.mkdir(parents=True)
    # Отметка в чужом срезе не засчитывается: проверка — по папке владельца ресурса.
    (other / "test_notes.py").write_text('@pytest.mark.isolation(resource="note")\n')

    assert missing_isolation_tests([fixture_feature()], tmp_path) == ["alpha: note"]


def test_a_marked_test_in_the_slice_passes_the_gate(tmp_path: Path) -> None:
    own = tmp_path / "features" / "alpha"
    own.mkdir(parents=True)
    (own / "test_notes.py").write_text('@pytest.mark.isolation(resource="note")\n')

    assert missing_isolation_tests([fixture_feature()], tmp_path) == []

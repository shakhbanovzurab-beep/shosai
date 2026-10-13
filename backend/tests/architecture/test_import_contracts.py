"""The import-linter contracts catch boundary violations (target architecture §5, §14 rule 12).

While there are no slices, the contracts run on a temporary `shosai` tree with two
features. The configuration is the backend's real pyproject.toml, not a copy of the rules.
"""

import os
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
LINT_IMPORTS = Path(sys.executable).with_name("lint-imports")
LAYERS = "Layers: entrypoints -> composition -> features -> core"
FEATURES = "Features meet through contracts"
PURE_KERNEL = "Pure kernel"
PURE_DOMAIN = "Pure slice domain"
CONTRACT_COUNT = 4
BASE_TREE = {
    "shosai.core.kernel.homes": "",
    # Домен опирается на ядро без фреймворков и на pydantic; адаптер среза — на домен.
    "shosai.features.alpha.domain.rules": "import pydantic\nimport shosai.core.kernel.homes\n",
    "shosai.features.alpha.service": (
        "import sqlalchemy\nimport shosai.features.alpha.domain.rules\n"
    ),
    # Контракт фичи вправе опираться на её внутренности: цепочка через контракт законна.
    "shosai.features.alpha.contracts": "import shosai.features.alpha.service\n",
    "shosai.features.beta.service": "import shosai.features.alpha.contracts\n",
    "shosai.composition.roles": "import shosai.features.beta.service\n",
    "shosai.entrypoints.cli": "import shosai.composition.roles\n",
}


def build_tree(root: Path, modules: Mapping[str, str]) -> None:
    """Write the tree's modules and packages and put the backend configuration next to them."""
    for module, source in modules.items():
        path = root.joinpath(*module.split(".")).with_suffix(".py")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        for package in path.parents:
            if package == root:
                break
            package.joinpath("__init__.py").touch()
    shutil.copy(BACKEND / "pyproject.toml", root / "pyproject.toml")


def lint_imports(root: Path) -> str:
    """Run lint-imports on the tree; the tree comes before the installed package on the path."""
    result = subprocess.run(
        [str(LINT_IMPORTS), "--config", str(root / "pyproject.toml"), "--no-cache"],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root)},
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    return f"exit={result.returncode}\n{result.stdout}{result.stderr}"


def test_the_layered_tree_keeps_every_contract(tmp_path: Path) -> None:
    build_tree(tmp_path, BASE_TREE)

    report = lint_imports(tmp_path)

    assert report.startswith("exit=0"), report
    assert f"Contracts: {CONTRACT_COUNT} kept, 0 broken." in report


@pytest.mark.parametrize(
    ("module", "source", "broken"),
    [
        ("shosai.features.beta.audit", "import shosai.features.alpha.service\n", FEATURES),
        ("shosai.features.alpha.listener", "import shosai.features.beta.service\n", FEATURES),
        ("shosai.core.kernel.clock", "import shosai.features.alpha.contracts\n", LAYERS),
        ("shosai.features.beta.cli", "import shosai.entrypoints.cli\n", LAYERS),
        ("shosai.shared.helpers", "", LAYERS),
        ("shosai.core.kernel.clock", "import sqlalchemy\n", PURE_KERNEL),
        ("shosai.core.kernel.clock", "from fastapi import FastAPI\n", PURE_KERNEL),
        ("shosai.features.beta.domain.sessions", "import sqlalchemy\n", PURE_DOMAIN),
        ("shosai.features.beta.domain", "from langgraph.graph import StateGraph\n", PURE_DOMAIN),
        # Косвенный путь тоже ломает контракт: домен → адаптер среза → SQLAlchemy.
        (
            "shosai.features.alpha.domain.plans",
            "import shosai.features.alpha.service\n",
            PURE_DOMAIN,
        ),
    ],
)
def test_a_boundary_violation_breaks_its_contract(
    tmp_path: Path, module: str, source: str, broken: str
) -> None:
    build_tree(tmp_path, {**BASE_TREE, module: source})

    report = lint_imports(tmp_path)

    assert report.startswith("exit=1"), report
    assert f"{broken} BROKEN" in report

"""The import-linter contracts catch boundary violations (target architecture §5, §14 rule 12).

The contracts run on a temporary `shosai` tree with two fixture features, so each rule
is proven on a violation the real tree does not contain. The configuration is the
backend's real pyproject.toml, not a copy of the rules.
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
PROVIDER_SDKS = "Provider SDKs only in core.ai"
LIGHT_AI = "Light AI value types"
LIGHT_TOOLS = "Light agent tool contract"
LIGHT_CONTRACTS = "Light slice contracts"
LANGGRAPH = "LangGraph only in the agent's turn frame"
CONTRACT_COUNT = 9
BASE_TREE = {
    "shosai.core.kernel.homes": "",
    # Порт ИИ: типы-значения лёгкие, SDK провайдера — в его адаптере, и это законно.
    "shosai.core.ai.calls": "import shosai.core.kernel.homes\n",
    "shosai.core.ai.requests": "",
    "shosai.core.ai.results": "import shosai.core.ai.calls\n",
    "shosai.core.ai.decisions": "import shosai.core.ai.results\n",
    "shosai.core.ai.documents": "import shosai.core.ai.results\n",
    "shosai.core.ai.adapters.live": "import websockets\nimport shosai.core.ai.results\n",
    # Контракт инструментов агента: pydantic и ядро без фреймворков — законно.
    "shosai.core.agent_tools.spec": "import pydantic\nimport shosai.core.kernel.homes\n",
    # Порты и реестр данных человека — значения без фреймворков (ADR 0045).
    "shosai.core.ports.keys": "",
    "shosai.core.account_data.spec": "",
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
        ("shosai.features.beta.domain.tokens", "import jwt\n", PURE_DOMAIN),
        ("shosai.features.beta.domain.passwords", "import bcrypt\n", PURE_DOMAIN),
        ("shosai.features.beta.speech", "import openai\n", PROVIDER_SDKS),
        ("shosai.composition.voice", "from google import genai\n", PROVIDER_SDKS),
        ("shosai.core.ai.requests", "import sqlalchemy\n", LIGHT_AI),
        ("shosai.core.ai.calls", "import httpx\n", LIGHT_AI),
        ("shosai.core.agent_tools.spec", "import sqlalchemy\n", LIGHT_TOOLS),
        ("shosai.core.agent_tools.context", "from fastapi import Depends\n", LIGHT_TOOLS),
        ("shosai.core.agent_tools.catalog", "import redis\n", LIGHT_TOOLS),
        (
            "shosai.core.agent_tools.bindings",
            "from langgraph.graph import StateGraph\n",
            LIGHT_TOOLS,
        ),
        ("shosai.features.beta.service", "from langgraph.graph import StateGraph\n", LANGGRAPH),
        ("shosai.composition.voice", "import langchain_core\n", LANGGRAPH),
        ("shosai.core.ports.directory", "import sqlalchemy\n", LIGHT_CONTRACTS),
        ("shosai.core.account_data.spec", "from fastapi import Depends\n", LIGHT_CONTRACTS),
    ],
)
def test_a_boundary_violation_breaks_its_contract(
    tmp_path: Path, module: str, source: str, broken: str
) -> None:
    build_tree(tmp_path, {**BASE_TREE, module: source})

    report = lint_imports(tmp_path)

    assert report.startswith("exit=1"), report
    assert f"{broken} BROKEN" in report


def test_a_contracts_package_is_public_with_its_submodules(tmp_path: Path) -> None:
    tree = {
        name: source
        for name, source in BASE_TREE.items()
        if name != "shosai.features.alpha.contracts"
    }
    tree |= {
        "shosai.features.alpha.contracts.__init__": "import shosai.features.alpha.service\n",
        "shosai.features.alpha.contracts.events": "import shosai.features.alpha.domain.rules\n",
        "shosai.features.beta.listener": "import shosai.features.alpha.contracts.events\n",
    }
    build_tree(tmp_path, tree)

    report = lint_imports(tmp_path)

    assert report.startswith("exit=0"), report


def test_a_slice_package_named_like_contracts_elsewhere_stays_private(tmp_path: Path) -> None:
    tree = {
        **BASE_TREE,
        "shosai.features.alpha.service.contracts": "",
        "shosai.features.beta.peek": "import shosai.features.alpha.service.contracts\n",
    }
    build_tree(tmp_path, tree)

    report = lint_imports(tmp_path)

    assert report.startswith("exit=1"), report
    assert f"{FEATURES} BROKEN" in report

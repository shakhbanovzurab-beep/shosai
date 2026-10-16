"""Prometheus rules rendered from the declarations, and the metrics every rule names (F5 §3.8).

- The generated rules under `deploy/observability/prometheus/rules/generated/` and dashboards
  under `deploy/observability/grafana/dashboards/generated/` equal a fresh render of the code;
  `--update-rules` rewrites both.
- Every backend metric a rule or a dashboard names — generated or written by hand — is one
  some role exports: the draft had alerts on metrics no process exposed, which could never fire.
- No exported metric carries a label Prometheus puts on the target (`job`, `instance`) or
  our scrape config does (`role`, `service`): Prometheus would rename it `exported_*`.
"""

import asyncio
import re
from contextlib import AsyncExitStack
from pathlib import Path

import pytest
from redis.asyncio import Redis

from shosai.composition.dashboards import rendered_dashboards
from shosai.composition.features import FEATURES
from shosai.composition.objectives import declared_rules
from shosai.core.observability.rule_files import render
from tests.composition.role_process import role_process
from tests.harness.database_access import DatabaseAccess
from tests.harness.process_environ import slot_environ
from tests.harness.run_slot import RunSlot
from tests.harness.settings import HarnessSettings

OBSERVABILITY = Path(__file__).parents[3] / "deploy" / "observability"
RULES = OBSERVABILITY / "prometheus" / "rules"
GENERATED = RULES / "generated"
DASHBOARDS = OBSERVABILITY / "grafana" / "dashboards" / "generated"
# Метрики бэкенда; node_, probe_, otelcol_ и другие экспортёры к каталогу ролей не относятся.
# Имя метки (после «{», «,» или «.» как в $labels.x, перед «=», «!», «~» или «:») — не метрика.
BACKEND_METRIC = re.compile(r"(?<![\w:{,.])(?:shosai|http_server)_[a-z0-9_]+(?![\w]|\s*[=!~:])")
TYPE_LINE = re.compile(r"^# TYPE (\S+) (\S+)$", re.MULTILINE)
SAMPLE_LABELS = re.compile(r"^[a-z_][a-z0-9_]*\{([^}]*)\}", re.MULTILINE)
LABEL_NAME = re.compile(r'([a-z_][a-z0-9_]*)="')
# Метки цели: job и instance ставит Prometheus, role и service — deploy/observability/prometheus.
TARGET_LABELS = frozenset({"job", "instance", "role", "service"})
SUFFIXES = {
    "counter": ("_total", "_created"),
    "histogram": ("_bucket", "_count", "_sum", "_created"),
    "summary": ("_count", "_sum", "_created"),
}
ROLES = {
    "api": ("api",),
    "ws": ("ws",),
    "workers": ("workers", "--queue", "default"),
    "scheduler": ("scheduler",),
}


def write_generated(directory: Path, current: dict[str, str]) -> None:
    """Rewrite a directory of generated files: stale ones go, current ones are written."""
    directory.mkdir(parents=True, exist_ok=True)
    for stale in {path.name for path in directory.glob("*.json")} - set(current):
        (directory / stale).unlink()
    for name, text in current.items():
        (directory / name).write_text(text, encoding="utf-8")


def recorded_files(directory: Path) -> dict[str, str]:
    return {path.name: path.read_text(encoding="utf-8") for path in directory.glob("*.json")}


def test_the_generated_rules_and_dashboards_match_the_declarations(
    request: pytest.FixtureRequest,
) -> None:
    rules = render(declared_rules(FEATURES))
    dashboards = rendered_dashboards(FEATURES)
    if request.config.getoption("--update-rules"):
        write_generated(GENERATED, rules)
        write_generated(DASHBOARDS, dashboards)

    assert (rules, dashboards) == (recorded_files(GENERATED), recorded_files(DASHBOARDS)), (
        "правила Prometheus или дашборды Grafana разошлись с кодом; перепишите их опцией "
        "--update-rules и закоммитьте вместе с изменением"
    )


def exported_names(exposition: str) -> set[str]:
    """Every sample name an exposition can carry, from its `# TYPE` lines."""
    names: set[str] = set()
    for family, kind in TYPE_LINE.findall(exposition):
        base = family.removesuffix("_total") if kind == "counter" else family
        names.add(family)
        names.update(base + suffix for suffix in SUFFIXES.get(kind, ()))
    return names


async def test_every_rule_names_a_metric_some_role_exports(
    run_slot: RunSlot,
    harness_settings: HarnessSettings,
    homes: DatabaseAccess,
    valkey: Redis,
    tmp_path: Path,
) -> None:
    # Роли пишут в слот (цены провайдеров, расписание); homes и valkey убирают это после теста.
    async with AsyncExitStack() as stack:
        running = [
            await stack.enter_async_context(
                role_process(
                    arguments,
                    slot_environ(run_slot, harness_settings),
                    tmp_path / f"{role}.log",
                )
            )
            for role, arguments in ROLES.items()
        ]
        await asyncio.gather(*(process.wait_ready() for process in running))
        expositions = [(await process.get("OPS_PORT", "/metrics")).text for process in running]
        for process in running:
            await process.stop()

    exported = set().union(*(exported_names(text) for text in expositions))
    labels = {
        name
        for text in expositions
        for label_set in SAMPLE_LABELS.findall(text)
        for name in LABEL_NAME.findall(label_set)
    }
    assert sorted(labels & TARGET_LABELS) == []
    named = {
        name
        for path in (*RULES.rglob("*"), *DASHBOARDS.rglob("*"))
        if path.is_file()
        for name in BACKEND_METRIC.findall(path.read_text(encoding="utf-8"))
    }
    assert named
    assert sorted(named - exported) == []

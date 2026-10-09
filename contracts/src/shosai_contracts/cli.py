"""Harness command line: `check` for slices, `render` for the baseline documents.

Exit codes: 0 — compatible (or the documents are up to date), 1 — errors found
(or the documents are out of date), 2 — invalid input.
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from shosai_contracts.check import check
from shosai_contracts.inputs import (
    DEFAULT_BASELINE,
    Scope,
    load_baseline,
    load_candidate,
    parse_acceptances,
)
from shosai_contracts.jsonvalue import ContractInputError, load_json
from shosai_contracts.model import Severity
from shosai_contracts.render_docs import render_baseline_documents
from shosai_contracts.render_report import render_json, render_text

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_INPUT = 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shosai-contracts",
        description="Check v2 API and WebSocket definitions against the draft contract baseline.",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE,
        help="baseline directory (default: contracts/draft)",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("check", help="compare v2 artifacts with the draft baseline")
    run.add_argument("--openapi", type=Path, help="v2 OpenAPI document (JSON)")
    run.add_argument("--routes", type=Path, help="v2 route snapshot: JSON array of 'METHOD /path'")
    run.add_argument("--websocket", type=Path, help="v2 WebSocket catalogue (JSON)")
    run.add_argument(
        "--slice",
        dest="slices",
        action="append",
        default=[],
        help="limit to operations owned by this slice, e.g. S04 (repeatable)",
    )
    run.add_argument(
        "--path-prefix",
        dest="prefixes",
        action="append",
        default=[],
        help="limit to paths with this prefix (repeatable)",
    )
    run.add_argument("--accept", type=Path, help="accepted deviations file (JSON)")
    run.add_argument("--format", choices=("text", "json"), default="text")
    run.add_argument(
        "--min-severity",
        choices=[item.value for item in Severity],
        default=Severity.INFO.value,
        help="hide findings below this severity",
    )

    render = commands.add_parser("render", help="regenerate the baseline's Markdown documents")
    render.add_argument(
        "--check",
        action="store_true",
        help="fail instead of writing when a document is out of date",
    )
    return parser


def _run_check(arguments: argparse.Namespace) -> int:
    if arguments.openapi is None and arguments.routes is None and arguments.websocket is None:
        raise ContractInputError("nothing to check: pass --openapi, --routes or --websocket")
    baseline = load_baseline(arguments.baseline)
    candidate = load_candidate(arguments.openapi, arguments.routes, arguments.websocket)
    acceptances = (
        {}
        if arguments.accept is None
        else parse_acceptances(load_json(arguments.accept), str(arguments.accept))
    )
    scope = Scope(slices=frozenset(arguments.slices), path_prefixes=tuple(arguments.prefixes))
    report = check(baseline, candidate, scope, acceptances)
    minimum = Severity(arguments.min_severity)
    render = render_json if arguments.format == "json" else render_text
    sys.stdout.write(render(report, scope, minimum))
    return EXIT_OK if report.is_compatible else EXIT_FAILED


def _run_render(arguments: argparse.Namespace) -> int:
    directory: Path = arguments.baseline
    stale: list[str] = []
    for name, content in render_baseline_documents(directory).items():
        target = directory / name
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        if current == content:
            continue
        stale.append(name)
        if not arguments.check:
            target.write_text(content, encoding="utf-8")
    if arguments.check and stale:
        sys.stderr.write(f"out of date: {', '.join(stale)}; run 'shosai-contracts render'\n")
        return EXIT_FAILED
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point of `shosai-contracts`."""
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "check":
            return _run_check(arguments)
        return _run_render(arguments)
    except ContractInputError as error:
        sys.stderr.write(f"input error: {error}\n")
        return EXIT_INPUT


if __name__ == "__main__":
    sys.exit(main())

"""Capture `draft/openapi.json` and `draft/routes.json` from the draft.

Runs under the interpreter of a throwaway draft environment (Python 3.12 and its
`requirements.txt`), not under the `contracts/` environment: the draft application
is built as is, its lifespan does not run, and no network or database is needed.

The production configuration is not used: every setting gets a fake local value
here, the working directory is an empty temporary one (the draft's `.env` file is
read relative to it and is not found), and the run goes under `env -i` so as not
to inherit the host's variables. The procedure is in the README.
"""

import argparse
import contextlib
import importlib
import inspect
import json
import os
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

# Формы регистрации как в production: без dev-маршрутов биллинга, без
# встроенной документации FastAPI (там /docs — справочный центр), со SPA.
SETTINGS = {
    "ENVIRONMENT": "dev",
    "DOCS_ENABLED": "false",
    "BILLING_DEV_MODE": "false",
    "DATABASE_URL": "postgresql+asyncpg://contracts:contracts@127.0.0.1:1/contracts_throwaway",
    "REDIS_URL": "redis://127.0.0.1:1/0",
    "REDIS_CACHE_URL": "",
    "REDIS_STATE_URL": "",
    "REDIS_LOCK_URL": "",
    "API_KEY_HASH": "",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "",
}
# HEAD и OPTIONS фреймворк добавляет сам; HEAD остаётся, если черновик описал его явно.
IMPLICIT_METHODS = frozenset({"HEAD", "OPTIONS"})

type Row = dict[str, str | bool]


class DraftRoute(Protocol):
    """A Starlette or FastAPI route; its other attributes depend on the route kind."""

    path: str


class DraftApplication(Protocol):
    """What the tool reads from the draft application.

    The draft's FastAPI types are not installed in the `contracts/` environment, so the
    application is described structurally and the route kind is told by class name.
    """

    routes: list[DraftRoute]

    def openapi(self) -> dict[str, object]:
        """OpenAPI document of the built application."""
        ...


def _source(endpoint: Callable[..., object], backend_src: Path) -> str:
    """Location of the handler in the draft repository: `backend/src/...:line`.

    A handler from a third-party library (for example, `/metrics`) has no location in
    the draft; the `module` field identifies it instead.
    """
    target = inspect.unwrap(endpoint)
    file = inspect.getsourcefile(target)
    if file is None or not Path(file).resolve().is_relative_to(backend_src):
        return ""
    line = inspect.getsourcelines(target)[1]
    relative = Path(file).resolve().relative_to(backend_src)
    return f"backend/src/{relative.as_posix()}:{line}"


def _endpoint_row(
    route: DraftRoute, method: str, kind: str, in_openapi: bool, backend_src: Path
) -> Row:
    """Row for a route with a handler."""
    endpoint = getattr(route, "endpoint", None)
    if not callable(endpoint):
        raise RuntimeError(f"route {route.path} has no endpoint")
    return {
        "method": method,
        "path": route.path,
        "kind": kind,
        "in_openapi": in_openapi,
        "module": str(endpoint.__module__),
        "source": _source(endpoint, backend_src),
    }


def _routes(app: DraftApplication, in_schema: set[tuple[str, str]], backend_src: Path) -> list[Row]:
    """Every route of the built application, one row per method."""
    rows: list[Row] = []
    for route in app.routes:
        kind = type(route).__name__
        if kind == "APIWebSocketRoute":
            rows.append(_endpoint_row(route, "WS", "websocket", False, backend_src))
        elif kind == "APIRoute":
            declared: set[str] = getattr(route, "methods", None) or set()
            methods = {
                method
                for method in declared
                if method not in IMPLICIT_METHODS or (method, route.path) in in_schema
            }
            rows += [
                _endpoint_row(route, method, "http", (method, route.path) in in_schema, backend_src)
                for method in sorted(methods)
            ]
        elif kind == "Mount":
            rows.append(
                {
                    "method": "GET",
                    "path": f"{route.path}/{{path:path}}",
                    "kind": "static_mount",
                    "in_openapi": False,
                    "module": type(getattr(route, "app", None)).__module__,
                    "source": "",
                }
            )
        else:
            raise RuntimeError(f"unexpected route type {kind} at {route.path}")
    return sorted(rows, key=lambda row: (str(row["path"]), str(row["method"])))


def _documented(schema: dict[str, object]) -> set[tuple[str, str]]:
    """The (method, path) pairs described in OpenAPI."""
    paths = schema.get("paths")
    if not isinstance(paths, dict):
        raise RuntimeError("the draft OpenAPI document has no paths")
    return {(str(method).upper(), str(path)) for path, item in paths.items() for method in item}


def main() -> int:
    """Build the draft application and write the OpenAPI document and the route table."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", type=Path, required=True, help="draft repository root")
    parser.add_argument("--out", type=Path, required=True, help="contracts/draft directory")
    arguments = parser.parse_args()
    backend_src = (arguments.draft / "backend" / "src").resolve()
    out = arguments.out.resolve()

    with (
        tempfile.TemporaryDirectory(prefix="draft-contract-") as workdir,
        contextlib.chdir(workdir),
    ):
        dist = Path(workdir) / "spa"
        (dist / "assets").mkdir(parents=True)
        (dist / "index.html").write_text("<!doctype html>", encoding="utf-8")
        os.environ.update(SETTINGS)
        os.environ["FRONTEND_DIST_DIR"] = str(dist)
        sys.path.insert(0, str(backend_src))
        app: DraftApplication = importlib.import_module("meetassist.main").create_app(testing=True)
        schema = app.openapi()
        routes = _routes(app, _documented(schema), backend_src)
        paths = len(_documented(schema))

    (out / "openapi.json").write_text(
        json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out / "routes.json").write_text(
        json.dumps(routes, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    sys.stdout.write(f"{paths} OpenAPI operations, {len(routes)} routes\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

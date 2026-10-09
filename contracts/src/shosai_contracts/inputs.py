"""Inputs of a check: the draft baseline, the v2 candidate, the scope and accepted deviations.

The baseline lives in `contracts/draft/`: the draft OpenAPI, the route classification
(`consumers.json`) and the WebSocket catalogue (`websocket.json`). The candidate is
the same set of artifacts exported from v2; any of them may be missing, and then its
part of the check is skipped and the report shows that in its coverage.
"""

from dataclasses import dataclass
from pathlib import Path

from shosai_contracts.http_check import normalize_path
from shosai_contracts.jsonvalue import (
    ContractInputError,
    Json,
    JsonObject,
    as_list,
    as_object,
    as_str,
    load_json,
    optional_str,
)
from shosai_contracts.model import CompatClass
from shosai_contracts.ws_catalogue import Endpoint, parse_catalogue

CONSUMERS_FORMAT = "whisperer-draft-consumers/1"
ACCEPTANCES_FORMAT = "whisperer-contract-acceptances/1"
DEFAULT_BASELINE = Path(__file__).resolve().parents[2] / "draft"

type RouteKey = tuple[str, str]


@dataclass(frozen=True, slots=True)
class BaselineOperation:
    """A draft route with its owning slice and consumer class."""

    method: str
    path: str
    in_openapi: bool
    slice_id: str
    compat_class: CompatClass

    @property
    def key(self) -> RouteKey:
        """Key for matching against v2 routes."""
        return self.method, normalize_path(self.path)

    @property
    def subject(self) -> str:
        """Label of the route in the report."""
        return f"{self.method} {self.path}"


@dataclass(frozen=True, slots=True)
class Baseline:
    """The recorded contract of the draft."""

    openapi: JsonObject
    operations: tuple[BaselineOperation, ...]
    websocket: tuple[Endpoint, ...]


@dataclass(frozen=True, slots=True)
class Candidate:
    """The v2 artifacts; `None` means one was not passed, and its part of the check is skipped."""

    openapi: JsonObject | None = None
    routes: frozenset[RouteKey] | None = None
    websocket: tuple[Endpoint, ...] | None = None


@dataclass(frozen=True, slots=True)
class Scope:
    """Which endpoints to check: owning slices and path prefixes (empty means all)."""

    slices: frozenset[str] = frozenset()
    path_prefixes: tuple[str, ...] = ()

    def includes(self, slice_id: str, path: str) -> bool:
        """Whether the endpoint is within the scope of the check."""
        if self.slices and slice_id not in self.slices:
            return False
        return not self.path_prefixes or path.startswith(self.path_prefixes)


def _operation(raw: Json, where: str) -> BaselineOperation:
    item = as_object(raw, where)
    try:
        compat_class = CompatClass(as_str(item.get("class"), f"{where}.class"))
    except ValueError as error:
        raise ContractInputError(f"{where}.class: {error}") from error
    if compat_class in {CompatClass.EXCLUDED, CompatClass.EXTERNAL} and not optional_str(
        item.get("reason")
    ):
        raise ContractInputError(f"{where}: class {compat_class} requires a reason")
    return BaselineOperation(
        method=as_str(item.get("method"), f"{where}.method"),
        path=as_str(item.get("path"), f"{where}.path"),
        in_openapi=item.get("in_openapi") is True,
        slice_id=as_str(item.get("slice"), f"{where}.slice"),
        compat_class=compat_class,
    )


def load_baseline(directory: Path = DEFAULT_BASELINE) -> Baseline:
    """Read the draft baseline from the `contracts/draft/` directory."""
    consumers = as_object(load_json(directory / "consumers.json"), "consumers.json")
    if consumers.get("format") != CONSUMERS_FORMAT:
        raise ContractInputError(f"consumers.json: format must be {CONSUMERS_FORMAT!r}")
    operations = tuple(
        _operation(item, f"consumers.json.operations[{index}]")
        for index, item in enumerate(as_list(consumers.get("operations"), "operations"))
    )
    return Baseline(
        openapi=as_object(load_json(directory / "openapi.json"), "openapi.json"),
        operations=operations,
        websocket=parse_catalogue(load_json(directory / "websocket.json"), "websocket.json"),
    )


def parse_routes(document: Json, origin: str) -> frozenset[RouteKey]:
    """The v2 route snapshot: an array of strings like `"GET /v1/me"`, `"WS /v1/ws/user"`."""
    routes: set[RouteKey] = set()
    for index, raw in enumerate(as_list(document, origin)):
        entry = as_str(raw, f"{origin}[{index}]")
        method, separator, path = entry.partition(" ")
        if not separator or not path.startswith("/"):
            raise ContractInputError(f"{origin}[{index}]: expected 'METHOD /path', got {entry!r}")
        routes.add((method.upper(), normalize_path(path)))
    return frozenset(routes)


def load_candidate(openapi: Path | None, routes: Path | None, websocket: Path | None) -> Candidate:
    """Read the v2 artifacts that were passed."""
    return Candidate(
        openapi=None if openapi is None else as_object(load_json(openapi), str(openapi)),
        routes=None if routes is None else parse_routes(load_json(routes), str(routes)),
        websocket=None
        if websocket is None
        else parse_catalogue(load_json(websocket), str(websocket)),
    )


def parse_acceptances(document: Json, origin: str) -> dict[str, str]:
    """Accepted deviations: finding identifier → reason (required)."""
    root = as_object(document, origin)
    if root.get("format") != ACCEPTANCES_FORMAT:
        raise ContractInputError(f"{origin}: format must be {ACCEPTANCES_FORMAT!r}")
    accepted: dict[str, str] = {}
    for index, raw in enumerate(as_list(root.get("accepted"), f"{origin}.accepted")):
        item = as_object(raw, f"{origin}.accepted[{index}]")
        finding_id = as_str(item.get("id"), f"{origin}.accepted[{index}].id")
        reason = as_str(item.get("reason"), f"{origin}.accepted[{index}].reason").strip()
        if not reason:
            raise ContractInputError(f"{origin}.accepted[{index}]: a reason is required")
        accepted[finding_id] = reason
    return accepted

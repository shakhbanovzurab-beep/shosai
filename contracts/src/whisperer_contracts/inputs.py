"""Входы проверки: база черновика, кандидат v2, область и принятые расхождения.

База лежит в `contracts/draft/`: OpenAPI черновика, классификация адресов
(`consumers.json`) и каталог WebSocket (`websocket.json`). Кандидат — те же
артефакты, выгруженные из v2; любой из них может отсутствовать, и тогда его
часть проверки не выполняется, а отчёт показывает это в покрытии.
"""

from dataclasses import dataclass
from pathlib import Path

from whisperer_contracts.http_check import normalize_path
from whisperer_contracts.jsonvalue import (
    ContractInputError,
    Json,
    JsonObject,
    as_list,
    as_object,
    as_str,
    load_json,
    optional_str,
)
from whisperer_contracts.model import CompatClass
from whisperer_contracts.ws_catalogue import Endpoint, parse_catalogue

CONSUMERS_FORMAT = "whisperer-draft-consumers/1"
ACCEPTANCES_FORMAT = "whisperer-contract-acceptances/1"
DEFAULT_BASELINE = Path(__file__).resolve().parents[2] / "draft"

type RouteKey = tuple[str, str]


@dataclass(frozen=True, slots=True)
class BaselineOperation:
    """Адрес черновика с владельцем-срезом и классом потребителя."""

    method: str
    path: str
    in_openapi: bool
    slice_id: str
    compat_class: CompatClass

    @property
    def key(self) -> RouteKey:
        """Ключ сопоставления с адресами v2."""
        return self.method, normalize_path(self.path)

    @property
    def subject(self) -> str:
        """Подпись адреса в отчёте."""
        return f"{self.method} {self.path}"


@dataclass(frozen=True, slots=True)
class Baseline:
    """Зафиксированный контракт черновика."""

    openapi: JsonObject
    operations: tuple[BaselineOperation, ...]
    websocket: tuple[Endpoint, ...]


@dataclass(frozen=True, slots=True)
class Candidate:
    """Артефакты v2; `None` — артефакт не передан, его часть проверки пропускается."""

    openapi: JsonObject | None = None
    routes: frozenset[RouteKey] | None = None
    websocket: tuple[Endpoint, ...] | None = None


@dataclass(frozen=True, slots=True)
class Scope:
    """Какие адреса проверять: срезы-владельцы и префиксы путей (пусто — все)."""

    slices: frozenset[str] = frozenset()
    path_prefixes: tuple[str, ...] = ()

    def includes(self, slice_id: str, path: str) -> bool:
        """Адрес входит в область проверки."""
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
    """Читает базу черновика из каталога `contracts/draft/`."""
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
    """Снимок маршрутов v2: массив строк `"GET /v1/me"`, `"WS /v1/ws/user"`."""
    routes: set[RouteKey] = set()
    for index, raw in enumerate(as_list(document, origin)):
        entry = as_str(raw, f"{origin}[{index}]")
        method, separator, path = entry.partition(" ")
        if not separator or not path.startswith("/"):
            raise ContractInputError(f"{origin}[{index}]: expected 'METHOD /path', got {entry!r}")
        routes.add((method.upper(), normalize_path(path)))
    return frozenset(routes)


def load_candidate(openapi: Path | None, routes: Path | None, websocket: Path | None) -> Candidate:
    """Читает переданные артефакты v2."""
    return Candidate(
        openapi=None if openapi is None else as_object(load_json(openapi), str(openapi)),
        routes=None if routes is None else parse_routes(load_json(routes), str(routes)),
        websocket=None
        if websocket is None
        else parse_catalogue(load_json(websocket), str(websocket)),
    )


def parse_acceptances(document: Json, origin: str) -> dict[str, str]:
    """Принятые расхождения: идентификатор находки → обоснование (обязательно)."""
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

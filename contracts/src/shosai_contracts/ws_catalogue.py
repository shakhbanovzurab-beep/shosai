"""Machine-readable catalogue of the WebSocket contract: its format and parsing.

OpenAPI does not describe WebSocket, so frames are recorded in a separate catalogue.
The draft baseline (`draft/websocket.json`) and v2 share one format: v2 exports its
catalogue from its frame descriptions, and the harness compares the two. Parsing
skips the documentation fields (`description`, `source`); the consumer class and
the slice are read only from the baseline.
"""

from dataclasses import dataclass
from enum import StrEnum

from shosai_contracts.jsonvalue import (
    ContractInputError,
    Json,
    JsonObject,
    as_list,
    as_object,
    as_str,
    optional_list,
    optional_str,
    str_list,
)
from shosai_contracts.model import CompatClass

CATALOGUE_FORMAT = "whisperer-websocket-catalogue/1"
JSON_TYPES = frozenset({"string", "integer", "number", "boolean", "object", "array", "null"})
ANY_TYPE = "any"


class FrameDirection(StrEnum):
    """Who sends the frame."""

    CLIENT_TO_SERVER = "client_to_server"
    SERVER_TO_CLIENT = "server_to_client"


class FrameEncoding(StrEnum):
    """How the frame travels over the connection."""

    JSON = "json"
    BINARY = "binary"
    TEXT = "text"


@dataclass(frozen=True, slots=True)
class FrameField:
    """A frame field or a connection parameter; an empty set of types means any type."""

    name: str
    types: frozenset[str]
    required: bool


@dataclass(frozen=True, slots=True)
class Frame:
    """One frame type in one direction."""

    direction: FrameDirection
    frame_type: str
    encoding: FrameEncoding
    binary_format: str
    fields: tuple[FrameField, ...]
    compat_class: CompatClass | None

    @property
    def key(self) -> tuple[FrameDirection, str]:
        """Key for matching draft and v2 frames."""
        return self.direction, self.frame_type


@dataclass(frozen=True, slots=True)
class CloseCode:
    """A connection close code or the HTTP status of a rejected handshake.

    Clients react to each in their own way: for shipped clients, a 401/403 status
    instead of 101 means "do not reconnect", so handshake statuses are part of the
    contract on a par with close codes.
    """

    code: int
    handled_by_clients: bool


@dataclass(frozen=True, slots=True)
class Endpoint:
    """A WebSocket endpoint with its connection, close codes and frames."""

    path: str
    discriminator: str
    auth: frozenset[str]
    query_params: tuple[FrameField, ...]
    close_codes: tuple[CloseCode, ...]
    handshake_rejections: tuple[CloseCode, ...]
    frames: tuple[Frame, ...]
    compat_class: CompatClass | None
    slice_id: str


def parse_types(raw: str, where: str) -> frozenset[str]:
    """Field type in the `string|null` notation; `any` means unconstrained."""
    parts = frozenset(part.strip() for part in raw.split("|"))
    if ANY_TYPE in parts:
        return frozenset()
    unknown = parts - JSON_TYPES
    if unknown:
        raise ContractInputError(f"{where}: unknown type(s) {sorted(unknown)}")
    return parts


def _field(raw: Json, where: str) -> FrameField:
    item = as_object(raw, where)
    return FrameField(
        name=as_str(item.get("name"), f"{where}.name"),
        types=parse_types(as_str(item.get("type"), f"{where}.type"), f"{where}.type"),
        required=item.get("required") is True,
    )


def _compat_class(item: JsonObject, where: str) -> CompatClass | None:
    raw = item.get("class")
    if raw is None:
        return None
    try:
        return CompatClass(as_str(raw, f"{where}.class"))
    except ValueError as error:
        raise ContractInputError(f"{where}.class: unknown class {raw!r}") from error


def _frame(raw: Json, where: str) -> Frame:
    item = as_object(raw, where)
    try:
        direction = FrameDirection(as_str(item.get("direction"), f"{where}.direction"))
        encoding = FrameEncoding(as_str(item.get("encoding"), f"{where}.encoding"))
    except ValueError as error:
        raise ContractInputError(f"{where}: {error}") from error
    return Frame(
        direction=direction,
        frame_type=as_str(item.get("type"), f"{where}.type"),
        encoding=encoding,
        binary_format=optional_str(item.get("binary_format")),
        fields=tuple(
            _field(field, f"{where}.fields[{index}]")
            for index, field in enumerate(optional_list(item.get("fields")))
        ),
        compat_class=_compat_class(item, where),
    )


def _close_code(raw: Json, where: str, key: str) -> CloseCode:
    item = as_object(raw, where)
    code = item.get(key)
    if not isinstance(code, int) or isinstance(code, bool):
        raise ContractInputError(f"{where}.{key}: expected an integer")
    return CloseCode(code=code, handled_by_clients=bool(optional_list(item.get("consumers"))))


def _endpoint(raw: Json, where: str) -> Endpoint:
    item = as_object(raw, where)
    frames = tuple(
        _frame(frame, f"{where}.frames[{index}]")
        for index, frame in enumerate(as_list(item.get("frames"), f"{where}.frames"))
    )
    keys = [frame.key for frame in frames]
    duplicates = sorted(
        {f"{direction}:{name}" for direction, name in keys if keys.count((direction, name)) > 1}
    )
    if duplicates:
        raise ContractInputError(f"{where}: duplicate frames {duplicates}")
    return Endpoint(
        path=as_str(item.get("path"), f"{where}.path"),
        discriminator=optional_str(item.get("discriminator")),
        auth=frozenset(str_list(item.get("auth"), f"{where}.auth")),
        query_params=tuple(
            _field(param, f"{where}.query_params[{index}]")
            for index, param in enumerate(optional_list(item.get("query_params")))
        ),
        close_codes=tuple(
            _close_code(code, f"{where}.close_codes[{index}]", "code")
            for index, code in enumerate(optional_list(item.get("close_codes")))
        ),
        handshake_rejections=tuple(
            _close_code(status, f"{where}.handshake_rejections[{index}]", "status")
            for index, status in enumerate(optional_list(item.get("handshake_rejections")))
        ),
        frames=frames,
        compat_class=_compat_class(item, where),
        slice_id=optional_str(item.get("slice")),
    )


def parse_catalogue(document: Json, origin: str) -> tuple[Endpoint, ...]:
    """Parse the catalogue; a wrong format is an explicit input error, not an empty catalogue."""
    root = as_object(document, origin)
    declared = root.get("format")
    if declared != CATALOGUE_FORMAT:
        raise ContractInputError(f"{origin}: format must be {CATALOGUE_FORMAT!r}, got {declared!r}")
    endpoints = tuple(
        _endpoint(endpoint, f"{origin}.endpoints[{index}]")
        for index, endpoint in enumerate(as_list(root.get("endpoints"), f"{origin}.endpoints"))
    )
    paths = [endpoint.path for endpoint in endpoints]
    if len(set(paths)) != len(paths):
        raise ContractInputError(f"{origin}: duplicate endpoint paths")
    return endpoints

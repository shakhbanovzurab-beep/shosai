"""`draft/websocket.md` из `draft/websocket.json`: каталог кадров для чтения человеком."""

from whisperer_contracts.jsonvalue import (
    Json,
    JsonObject,
    optional_list,
    optional_object,
    optional_str,
)
from whisperer_contracts.render_markdown import (
    CLASS_LEGEND,
    GENERATED_NOTICE,
    code,
    consumers_by_client,
    reference,
    references,
    table,
)

DIRECTIONS = (
    ("client_to_server", "Client → server frames"),
    ("server_to_client", "Server → client frames"),
)


def _objects(value: Json) -> list[JsonObject]:
    return [optional_object(item) for item in optional_list(value)]


def _summary(endpoints: list[JsonObject]) -> list[str]:
    rows: list[tuple[str, ...]] = []
    for endpoint in endpoints:
        frames = _objects(endpoint.get("frames"))
        rows.append(
            (
                f"[`{optional_str(endpoint.get('path'))}`](#{_anchor(endpoint)})",
                optional_str(endpoint.get("slice")),
                optional_str(endpoint.get("class")),
                ", ".join(code(item) for item in sorted(_strings(endpoint.get("auth")))) or "—",
                str(sum(1 for item in frames if item.get("direction") == "client_to_server")),
                str(sum(1 for item in frames if item.get("direction") == "server_to_client")),
                ", ".join(str(item.get("code")) for item in _objects(endpoint.get("close_codes")))
                or "—",
            )
        )
    return table(
        ("Path", "Slice", "Class", "Auth", "Client frames", "Server frames", "Close codes"), rows
    )


def _anchor(endpoint: JsonObject) -> str:
    path = optional_str(endpoint.get("path"))
    return "".join(char for char in path.lower() if char.isalnum() or char in "-_ ").replace(
        " ", "-"
    )


def _auth(endpoint: JsonObject) -> str:
    return ", ".join(code(item) for item in _strings(endpoint.get("auth"))) or "—"


def _strings(value: Json) -> list[str]:
    return [item for item in optional_list(value) if isinstance(item, str)]


def _fields(fields: list[JsonObject]) -> list[str]:
    return table(
        ("Field", "Type", "Required", "Meaning"),
        [
            (
                code(optional_str(item.get("name"))),
                code(optional_str(item.get("type"))),
                "yes" if item.get("required") is True else "no",
                optional_str(item.get("description")),
            )
            for item in fields
        ],
    )


def _frame(frame: JsonObject) -> list[str]:
    encoding = optional_str(frame.get("encoding"))
    binary = optional_str(frame.get("binary_format"))
    lines = [
        "",
        f"#### `{optional_str(frame.get('type'))}`",
        "",
        f"{encoding}{f', layout {code(binary)}' if binary else ''} · class "
        f"`{optional_str(frame.get('class')) or 'endpoint'}` · source {reference(_source(frame))}",
        "",
        optional_str(frame.get("description")) or "_No description._",
        "",
        f"Consumers: {references(optional_list(frame.get('consumers')))}",
        "",
    ]
    return lines + _fields(_objects(frame.get("fields")))


def _source(item: JsonObject) -> JsonObject:
    """`source` хранится строкой `file:line`; для ссылки разбирается обратно."""
    file, _, line = optional_str(item.get("source")).rpartition(":")
    return (
        {"file": file, "line": int(line)}
        if line.isdigit()
        else {"file": optional_str(item.get("source"))}
    )


def _endpoint(endpoint: JsonObject) -> list[str]:
    path = optional_str(endpoint.get("path"))
    lines = [
        "",
        f"## {path}",
        "",
        f"- **Slice:** {optional_str(endpoint.get('slice'))} · **class:** "
        f"`{optional_str(endpoint.get('class'))}` · **source:** {reference(_source(endpoint))}",
        f"- **Consumers:** {consumers_by_client(endpoint.get('consumers'))}",
        f"- **Authentication:** {_auth(endpoint)}. {optional_str(endpoint.get('auth_details'))}",
        f"- **Discriminator:** {code(optional_str(endpoint.get('discriminator')))}",
        f"- **Handshake:** {optional_str(endpoint.get('handshake')) or '—'}",
        f"- **Protocol version:** {optional_str(endpoint.get('protocol_version')) or '—'}",
        f"- **Resume:** {optional_str(endpoint.get('resume')) or '—'}",
        "",
        "### Query parameters",
        "",
    ]
    lines += _fields(_objects(endpoint.get("query_params")))
    lines += ["", "### Close codes", ""]
    lines += table(
        ("Code", "Reason", "When", "Source", "Handled by"),
        [
            (
                str(item.get("code")),
                optional_str(item.get("reason")),
                optional_str(item.get("when")),
                reference(_source(item)),
                consumers_by_client(item.get("consumers")),
            )
            for item in _objects(endpoint.get("close_codes"))
        ],
    )
    lines += ["", "### Handshake rejections", ""]
    lines += table(
        ("HTTP status", "Reason", "When", "Source", "Handled by"),
        [
            (
                str(item.get("status")),
                optional_str(item.get("reason")),
                optional_str(item.get("when")),
                reference(_source(item)),
                consumers_by_client(item.get("consumers")),
            )
            for item in _objects(endpoint.get("handshake_rejections"))
        ],
    )
    lines += ["", "### Limits", ""]
    lines += table(
        ("Limit", "Value", "Source"),
        [
            (
                optional_str(item.get("name")),
                optional_str(item.get("value")),
                reference(_source(item)),
            )
            for item in _objects(endpoint.get("limits"))
        ],
    )
    frames = _objects(endpoint.get("frames"))
    for direction, title in DIRECTIONS:
        lines += ["", f"### {title}"]
        for frame in frames:
            if frame.get("direction") == direction:
                lines += _frame(frame)
    return lines


def render_websocket(document: JsonObject, preamble: str) -> str:
    """Полный текст `websocket.md`."""
    endpoints = _objects(document.get("endpoints"))
    lines = [
        GENERATED_NOTICE.format(source="websocket.json"),
        "",
        "# Draft WebSocket contract",
        "",
        preamble,
        "",
        CLASS_LEGEND,
        "## Endpoints",
        "",
    ]
    lines += _summary(endpoints)
    for endpoint in endpoints:
        lines += _endpoint(endpoint)
    lines += [
        "",
        "## Frames clients handle that the draft server never sends",
        "",
        "Not a contract obligation: v2 may keep not sending them.",
        "",
    ]
    lines += table(
        ("Client", "Endpoint", "Direction", "Frame", "Where", "Note"),
        [
            (
                code(optional_str(item.get("client"))),
                code(optional_str(item.get("path"))),
                optional_str(item.get("direction")),
                code(optional_str(item.get("frame"))),
                reference(item),
                optional_str(item.get("note")),
            )
            for item in _objects(document.get("unmatched_frames"))
        ],
    )
    return "\n".join(lines) + "\n"

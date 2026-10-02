"""`draft/consumers.md` from `draft/consumers.json`: route classification and consumers."""

from whisperer_contracts.http_check import (
    Operation,
    normalize_path,
    operations,
    response_is_untyped,
)
from whisperer_contracts.jsonvalue import (
    Json,
    JsonObject,
    optional_list,
    optional_object,
    optional_str,
)
from whisperer_contracts.model import CLASS_STRENGTH, CompatClass
from whisperer_contracts.render_markdown import (
    CLASS_LEGEND,
    GENERATED_NOTICE,
    code,
    consumers_by_client,
    reference,
    references,
    table,
)
from whisperer_contracts.schema_shape import SchemaDocument

CLASS_TITLES = {
    CompatClass.NATIVE: "Used by shipped native clients — must stay compatible",
    CompatClass.EXTERNAL: "Used by external integrations — must stay compatible",
    CompatClass.WEB: "Used by the web frontend only — may change with the v2 frontend",
    CompatClass.UNUSED: "Unused — no consumer found",
    CompatClass.EXCLUDED: "Excluded from the contract",
}


def _objects(value: Json) -> list[JsonObject]:
    return [optional_object(item) for item in optional_list(value)]


def _subject(item: JsonObject) -> str:
    return f"`{optional_str(item.get('method'))} {optional_str(item.get('path'))}`"


def _summary(items: list[JsonObject]) -> list[str]:
    rows: list[tuple[str, ...]] = []
    for compat_class in CLASS_STRENGTH:
        chosen = [item for item in items if item.get("class") == compat_class.value]
        documented = sum(1 for item in chosen if item.get("in_openapi") is True)
        rows.append(
            (
                code(compat_class.value),
                str(documented),
                str(len(chosen) - documented),
                str(len(chosen)),
            )
        )
    rows.append(
        (
            "**total**",
            str(sum(1 for item in items if item.get("in_openapi") is True)),
            str(sum(1 for item in items if item.get("in_openapi") is not True)),
            str(len(items)),
        )
    )
    return table(("Class", "In OpenAPI", "Outside OpenAPI", "Total"), rows)


def _clients(clients: list[JsonObject]) -> list[str]:
    lines = table(
        ("Client", "Kind", "Codebase", "Shipped", "How it reaches users"),
        [
            (
                code(optional_str(item.get("id"))),
                optional_str(item.get("kind")),
                code(optional_str(item.get("codebase"))),
                "yes" if item.get("shipped") is True else "no",
                optional_str(item.get("deployment")),
            )
            for item in clients
        ],
    )
    for item in clients:
        lines += ["", f"### {optional_str(item.get('id'))} — {optional_str(item.get('name'))}", ""]
        lines += [optional_str(item.get("notes")) or "_No notes._", "", "Shipped evidence:", ""]
        lines += table(
            ("Evidence", "Where"),
            [
                (optional_str(entry.get("what")), reference(entry))
                for entry in _objects(item.get("evidence"))
            ],
        )
        lines += ["", "Headers sent:", ""]
        lines += table(
            ("Header", "Value", "Where"),
            [
                (
                    code(optional_str(entry.get("name"))),
                    optional_str(entry.get("value")),
                    reference(entry),
                )
                for entry in _objects(item.get("headers"))
            ],
        )
    return lines


def _by_class(items: list[JsonObject]) -> list[str]:
    lines: list[str] = []
    for compat_class in CLASS_STRENGTH:
        chosen = [item for item in items if item.get("class") == compat_class.value]
        lines += ["", f"### {CLASS_TITLES[compat_class]} ({len(chosen)})", ""]
        lines += table(
            ("Operation", "Slice", "OpenAPI", "Consumers", "Reason", "Draft source"),
            [
                (
                    _subject(item),
                    optional_str(item.get("slice")),
                    "yes" if item.get("in_openapi") is True else "no",
                    consumers_by_client(item.get("consumers")),
                    optional_str(item.get("reason")),
                    code(optional_str(item.get("source"))),
                )
                for item in chosen
            ],
        )
    return lines


def _by_client(items: list[JsonObject], clients: list[JsonObject]) -> list[str]:
    lines: list[str] = []
    for client in clients:
        client_id = optional_str(client.get("id"))
        rows: list[tuple[str, ...]] = []
        for item in items:
            mine = [
                ref for ref in _objects(item.get("consumers")) if ref.get("client") == client_id
            ]
            if mine:
                rows.append((_subject(item), optional_str(item.get("class")), references(mine)))
        lines += ["", f"### {client_id} ({len(rows)} operations)", ""]
        lines += table(("Operation", "Class", "Call sites"), rows)
    return lines


def _absent(routes: list[JsonObject]) -> list[str]:
    return table(
        ("Route", "Reason", "Draft source"),
        [
            (
                _subject(item),
                optional_str(item.get("reason")),
                code(optional_str(item.get("source"))),
            )
            for item in routes
        ],
    )


def _unmatched(unmatched: list[JsonObject]) -> list[str]:
    return table(
        ("Client", "Call", "Where", "Why it matches no route"),
        [
            (
                code(optional_str(item.get("client"))),
                code(optional_str(item.get("raw"))),
                reference(item),
                optional_str(item.get("why")),
            )
            for item in unmatched
        ],
    )


def _untyped(items: list[JsonObject], openapi: JsonObject) -> list[str]:
    """Must-keep operations whose response the draft did not describe with a schema."""
    document = SchemaDocument(openapi)
    index: dict[tuple[str, str], Operation] = operations(openapi)
    rows: list[tuple[str, ...]] = []
    for item in items:
        if not CompatClass(optional_str(item.get("class"))).must_stay_compatible:
            continue
        key = (optional_str(item.get("method")), normalize_path(optional_str(item.get("path"))))
        operation = index.get(key)
        if operation is not None and response_is_untyped(document, operation):
            rows.append(
                (
                    _subject(item),
                    optional_str(item.get("slice")),
                    optional_str(item.get("class")),
                    consumers_by_client(item.get("consumers")),
                )
            )
    return table(("Operation", "Slice", "Class", "Consumers"), rows)


def render_consumers(document: JsonObject, openapi: JsonObject, preamble: str) -> str:
    """Full text of `consumers.md`."""
    items = _objects(document.get("operations"))
    clients = _objects(document.get("clients"))
    lines = [
        GENERATED_NOTICE.format(source="consumers.json"),
        "",
        "# Draft API consumers and compatibility classes",
        "",
        preamble,
        "",
        CLASS_LEGEND,
        "## Summary",
        "",
        *_summary(items),
        "",
        "## Clients",
        "",
        *_clients(clients),
        "",
        "## Operations by class",
        *_by_class(items),
        "",
        "### Routes absent from production",
        "",
        "These exist in the draft code but are not registered in production, so they are not "
        "in the OpenAPI document or the route table.",
        "",
        *_absent(_objects(document.get("excluded_routes"))),
        "",
        "## Usage by client",
        "",
        "Every call site found in each client, with the draft file and line.",
        *_by_client(items, clients),
        "",
        "## Client calls that match no draft route",
        "",
        *_unmatched(_objects(document.get("unmatched"))),
        "",
        "## Must-keep operations with untyped draft responses",
        "",
        "The draft declares no response schema for these, so the harness cannot compare their "
        "shape. The owning slice verifies them against recorded responses (D2 fixtures) and the "
        "fields the clients read.",
        "",
        *_untyped(items, openapi),
    ]
    return "\n".join(lines) + "\n"

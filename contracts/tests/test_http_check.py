"""Сравнение HTTP-операций: сопоставление путей, параметры, тело, ответ."""

from whisperer_contracts.http_check import (
    compare_operation,
    normalize_path,
    operations,
    response_is_untyped,
)
from whisperer_contracts.jsonvalue import JsonObject
from whisperer_contracts.schema_compare import DocumentPair
from whisperer_contracts.schema_shape import SchemaDocument


def document(path: str, method: str, operation: JsonObject) -> JsonObject:
    return {"openapi": "3.1.0", "paths": {path: {method: operation}}}


def json_body(schema: JsonObject, *, required: bool = True) -> JsonObject:
    return {"required": required, "content": {"application/json": {"schema": schema}}}


def ok(schema: JsonObject, code: str = "200") -> JsonObject:
    return {code: {"description": "ok", "content": {"application/json": {"schema": schema}}}}


def query(name: str, *, required: bool, kind: str = "string") -> JsonObject:
    return {"name": name, "in": "query", "required": required, "schema": {"type": kind}}


ITEM: JsonObject = {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}


def diff(draft: JsonObject, candidate: JsonObject) -> list[str]:
    draft_op = next(iter(operations(draft).values()))
    candidate_op = next(iter(operations(candidate).values()))
    pair = DocumentPair(SchemaDocument(draft), SchemaDocument(candidate))
    return [
        f"{item.rule}@{item.pointer}" for item in compare_operation(pair, draft_op, candidate_op)
    ]


def test_path_parameters_match_by_position_not_name() -> None:
    assert normalize_path("/v1/me/sessions/{session_id}/note") == "/v1/me/sessions/{}/note"
    assert normalize_path("/app/{full_path:path}") == "/app/{}"
    draft = document(
        "/v1/x/{session_id}",
        "get",
        {
            "parameters": [
                {"name": "session_id", "in": "path", "required": True, "schema": {"type": "string"}}
            ],
            "responses": ok(ITEM),
        },
    )
    candidate = document(
        "/v1/x/{id}",
        "get",
        {
            "parameters": [
                {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}
            ],
            "responses": ok(ITEM),
        },
    )
    assert set(operations(draft)) == set(operations(candidate))
    assert diff(draft, candidate) == []


def test_query_parameter_rules() -> None:
    draft = document(
        "/v1/x", "get", {"parameters": [query("limit", required=False)], "responses": ok(ITEM)}
    )
    stricter = document(
        "/v1/x",
        "get",
        {
            "parameters": [query("limit", required=False), query("cursor", required=True)],
            "responses": ok(ITEM),
        },
    )
    assert diff(draft, stricter) == ["request.parameter_newly_required@query.cursor"]
    dropped = document("/v1/x", "get", {"responses": ok(ITEM)})
    assert diff(draft, dropped) == ["request.parameter_ignored@query.limit"]
    retyped = document(
        "/v1/x",
        "get",
        {"parameters": [query("limit", required=False, kind="integer")], "responses": ok(ITEM)},
    )
    assert diff(draft, retyped) == ["request.type_changed@query.limit"]


def test_header_names_are_case_insensitive() -> None:
    header: JsonObject = {
        "name": "X-Client-Kind",
        "in": "header",
        "required": False,
        "schema": {"type": "string"},
    }
    lower: JsonObject = {
        "name": "x-client-kind",
        "in": "header",
        "required": False,
        "schema": {"type": "string"},
    }
    draft = document("/v1/x", "post", {"parameters": [header], "responses": ok(ITEM)})
    candidate = document("/v1/x", "post", {"parameters": [lower], "responses": ok(ITEM)})
    assert diff(draft, candidate) == []


def test_body_rules() -> None:
    draft = document(
        "/v1/x", "post", {"requestBody": json_body(ITEM, required=False), "responses": ok(ITEM)}
    )
    required = document("/v1/x", "post", {"requestBody": json_body(ITEM), "responses": ok(ITEM)})
    assert diff(draft, required) == ["request.body_newly_required@body"]
    multipart = document(
        "/v1/x",
        "post",
        {
            "requestBody": {"content": {"multipart/form-data": {"schema": ITEM}}},
            "responses": ok(ITEM),
        },
    )
    assert diff(draft, multipart) == ["request.media_type_removed@body[application/json]"]
    none = document("/v1/x", "post", {"responses": ok(ITEM)})
    assert diff(draft, none) == ["request.body_ignored@body"]


def test_media_type_parameters_are_ignored() -> None:
    draft = document(
        "/v1/x",
        "get",
        {
            "responses": {
                "200": {
                    "description": "ok",
                    "content": {"application/json; charset=utf-8": {"schema": ITEM}},
                }
            }
        },
    )
    candidate = document("/v1/x", "get", {"responses": ok(ITEM)})
    assert diff(draft, candidate) == []


def test_response_status_and_shape() -> None:
    draft = document("/v1/x", "post", {"responses": ok(ITEM)})
    created = document("/v1/x", "post", {"responses": ok(ITEM, "201")})
    assert diff(draft, created) == ["response.status_changed@response"]
    stream = document(
        "/v1/x",
        "post",
        {
            "responses": {
                "200": {
                    "description": "ok",
                    "content": {"text/event-stream": {"schema": {"type": "string"}}},
                }
            }
        },
    )
    assert diff(draft, stream) == ["response.media_type_changed@response.200[application/json]"]
    slimmer = document("/v1/x", "post", {"responses": ok({"type": "object", "properties": {}})})
    assert diff(draft, slimmer) == ["response.property_removed@response.200.id"]


def test_untyped_response_detection() -> None:
    typed = document("/v1/x", "get", {"responses": ok(ITEM)})
    untyped = document("/v1/x", "get", {"responses": ok({})})
    empty = document("/v1/x", "delete", {"responses": {"204": {"description": "gone"}}})
    for doc, expected in ((typed, False), (untyped, True), (empty, True)):
        operation = next(iter(operations(doc).values()))
        assert response_is_untyped(SchemaDocument(doc), operation) is expected


def test_stream_item_schemas_are_compared() -> None:
    event: JsonObject = {
        "type": "object",
        "properties": {"data": {"type": "string"}, "event": {"type": "string"}},
        "required": ["data"],
    }
    draft = document(
        "/v1/x",
        "post",
        {
            "responses": {
                "200": {
                    "description": "ok",
                    "content": {"text/event-stream": {"itemSchema": event}},
                }
            }
        },
    )
    candidate = document(
        "/v1/x",
        "post",
        {
            "responses": {
                "200": {
                    "description": "ok",
                    "content": {
                        "text/event-stream": {
                            "itemSchema": {
                                "type": "object",
                                "properties": {"data": {"type": "string"}},
                            }
                        }
                    },
                }
            }
        },
    )
    assert diff(draft, candidate) == [
        "response.property_no_longer_required@response.200.data",
        "response.optional_property_removed@response.200.event",
    ]

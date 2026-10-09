"""Comparison of one draft HTTP operation with the v2 operation using the OpenAPI documents.

Operations are matched by method and by the path template without parameter names:
`/v1/me/sessions/{session_id}` and `/v1/me/sessions/{id}` are the same endpoint for
a client. Path parameters are compared by position, the others by location and name.
Error responses are not compared: the draft describes only 422 in OpenAPI, and the
shape of the v2 error envelope is a separate decision (see README).
"""

import re
from dataclasses import dataclass

from shosai_contracts.jsonvalue import JsonObject, optional_list, optional_object, optional_str
from shosai_contracts.model import Difference, Impact
from shosai_contracts.schema_compare import DocumentPair
from shosai_contracts.schema_rules import Direction
from shosai_contracts.schema_shape import SchemaDocument

HTTP_METHODS = ("get", "put", "post", "delete", "patch", "options", "head", "trace")
_PATH_PARAMETER = re.compile(r"\{([^}:]+)(?::[^}]+)?\}")


def normalize_path(path: str) -> str:
    """Path template without parameter names, as a client sees it."""
    return _PATH_PARAMETER.sub("{}", path)


@dataclass(frozen=True, slots=True)
class Operation:
    """An operation of an OpenAPI document with its original path template."""

    method: str
    path: str
    spec: JsonObject
    path_parameters: JsonObject

    @property
    def key(self) -> tuple[str, str]:
        """Matching key: the method and the normalized path."""
        return self.method, normalize_path(self.path)


def operations(document: JsonObject) -> dict[tuple[str, str], Operation]:
    """Every operation of the document by its matching key."""
    found: dict[tuple[str, str], Operation] = {}
    for path, raw_item in optional_object(document.get("paths")).items():
        item = optional_object(raw_item)
        for method in HTTP_METHODS:
            if method in item:
                operation = Operation(method.upper(), path, optional_object(item[method]), item)
                found[operation.key] = operation
    return found


@dataclass(frozen=True, slots=True)
class Parameter:
    """A request parameter reduced to its matching key."""

    key: str
    required: bool
    schema: JsonObject


def _parameters(document: SchemaDocument, operation: Operation) -> dict[str, Parameter]:
    """Operation parameters: path ones by position, headers case-insensitively."""
    raw = optional_list(operation.path_parameters.get("parameters"))
    raw += optional_list(operation.spec.get("parameters"))
    positions = {name: index for index, name in enumerate(_PATH_PARAMETER.findall(operation.path))}
    found: dict[str, Parameter] = {}
    for item in raw:
        parameter, _ = document.resolve(optional_object(item))
        name = optional_str(parameter.get("name"))
        location = optional_str(parameter.get("in"))
        if location == "path":
            key = f"path[{positions.get(name, name)}]"
        elif location == "header":
            key = f"header.{name.lower()}"
        else:
            key = f"{location}.{name}"
        found[key] = Parameter(
            key=key,
            required=parameter.get("required") is True or location == "path",
            schema=optional_object(parameter.get("schema")),
        )
    return found


def _media(content: JsonObject) -> dict[str, JsonObject]:
    """Schemas by content type; media type parameters (`; charset`) are dropped.

    For streams (`text/event-stream`, JSON Lines) FastAPI describes the schema of one
    item in `itemSchema`, not of the whole body in `schema`.
    """
    found: dict[str, JsonObject] = {}
    for media, raw in content.items():
        entry = optional_object(raw)
        schema = entry.get("schema", entry.get("itemSchema"))
        found[media.split(";", 1)[0].strip().lower()] = optional_object(schema)
    return found


def _request_body(
    document: SchemaDocument, operation: Operation
) -> tuple[bool, dict[str, JsonObject]]:
    """Whether the request body is required, and its schemas by content type."""
    raw = optional_object(operation.spec.get("requestBody"))
    if not raw:
        return False, {}
    body, _ = document.resolve(raw)
    return body.get("required") is True, _media(optional_object(body.get("content")))


def primary_response(
    document: SchemaDocument, operation: Operation
) -> tuple[str, dict[str, JsonObject]] | None:
    """The primary successful response: the lowest 2xx code, otherwise 3xx."""
    responses = optional_object(operation.spec.get("responses"))
    codes = sorted(code for code in responses if code[:1] in {"2", "3"} and code[1:].isdigit())
    success = [code for code in codes if code.startswith("2")] or codes
    if not success:
        return None
    response, _ = document.resolve(optional_object(responses[success[0]]))
    return success[0], _media(optional_object(response.get("content")))


def response_is_untyped(document: SchemaDocument, operation: Operation) -> bool:
    """The draft did not describe the successful response's shape; no schema can protect it."""
    primary = primary_response(document, operation)
    if primary is None:
        return True
    _, media = primary
    return not media or all(document.shape(schema).is_any for schema in media.values())


def compare_operation(
    documents: DocumentPair, draft: Operation, candidate: Operation
) -> list[Difference]:
    """Every difference between the v2 operation and the draft operation."""
    differences = _compare_parameters(documents, draft, candidate)
    differences += _compare_body(documents, draft, candidate)
    differences += _compare_response(documents, draft, candidate)
    return differences


def _compare_parameters(
    documents: DocumentPair, draft: Operation, candidate: Operation
) -> list[Difference]:
    draft_parameters = _parameters(documents.draft, draft)
    candidate_parameters = _parameters(documents.candidate, candidate)
    differences: list[Difference] = []
    for key, parameter in sorted(candidate_parameters.items()):
        previous = draft_parameters.get(key)
        if parameter.required and (previous is None or not previous.required):
            differences.append(
                Difference(
                    "request.parameter_newly_required",
                    Impact.BREAKING,
                    key,
                    f"v2 requires parameter '{key}', which draft clients may not send",
                )
            )
    for key, parameter in sorted(draft_parameters.items()):
        current = candidate_parameters.get(key)
        if current is None:
            differences.append(
                Difference(
                    "request.parameter_ignored",
                    Impact.RISKY,
                    key,
                    f"draft clients send parameter '{key}'; v2 no longer reads it",
                )
            )
            continue
        differences += documents.compare(parameter.schema, current.schema, Direction.REQUEST, key)
    return differences


def _compare_body(
    documents: DocumentPair, draft: Operation, candidate: Operation
) -> list[Difference]:
    draft_required, draft_media = _request_body(documents.draft, draft)
    candidate_required, candidate_media = _request_body(documents.candidate, candidate)
    differences: list[Difference] = []
    if candidate_required and not draft_required:
        differences.append(
            Difference(
                "request.body_newly_required",
                Impact.BREAKING,
                "body",
                "v2 requires a request body that draft clients may not send",
            )
        )
    if draft_media and not candidate_media:
        differences.append(
            Difference(
                "request.body_ignored",
                Impact.RISKY,
                "body",
                "draft clients send a request body; v2 declares none",
            )
        )
        return differences
    for media, schema in sorted(draft_media.items()):
        current = candidate_media.get(media)
        if current is None:
            differences.append(
                Difference(
                    "request.media_type_removed",
                    Impact.BREAKING,
                    f"body[{media}]",
                    f"draft clients send '{media}'; v2 does not accept it",
                )
            )
            continue
        differences += documents.compare(schema, current, Direction.REQUEST, "body")
    return differences


def _compare_response(
    documents: DocumentPair, draft: Operation, candidate: Operation
) -> list[Difference]:
    draft_primary = primary_response(documents.draft, draft)
    candidate_primary = primary_response(documents.candidate, candidate)
    if draft_primary is None:
        return []
    draft_code, draft_media = draft_primary
    if candidate_primary is None or candidate_primary[0] != draft_code:
        found = "none" if candidate_primary is None else candidate_primary[0]
        return [
            Difference(
                "response.status_changed",
                Impact.BREAKING,
                "response",
                f"draft returns {draft_code} on success; v2 returns {found}",
            )
        ]
    differences: list[Difference] = []
    _, candidate_media = candidate_primary
    pointer = f"response.{draft_code}"
    for media, schema in sorted(draft_media.items()):
        current = candidate_media.get(media)
        if current is None:
            differences.append(
                Difference(
                    "response.media_type_changed",
                    Impact.BREAKING,
                    f"{pointer}[{media}]",
                    f"draft clients read '{media}'; v2 does not return it",
                )
            )
            continue
        differences += documents.compare(schema, current, Direction.RESPONSE, pointer)
    return differences

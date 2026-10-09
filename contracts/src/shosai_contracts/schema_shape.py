"""Normalization of JSON Schema from OpenAPI 3.1 into a flat "shape" for comparison.

FastAPI and Pydantic write the same data shape in different ways: a `$ref` to a
component, an `allOf` with one member, `anyOf [X, null]` instead of nullable, `type`
as a string or a list. Comparing raw schemas would catch these differences in
notation instead of differences in the contract, so a schema is first reduced to a
`Shape`: a set of types, nullable, properties, array items, an enumeration, union
variants.
"""

import json
from dataclasses import dataclass, replace

from shosai_contracts.jsonvalue import (
    ContractInputError,
    Json,
    JsonObject,
    optional_list,
    optional_object,
    optional_str,
    str_list,
)

MAX_REF_CHAIN = 32
REF_PREFIX = "#/"


@dataclass(frozen=True, slots=True)
class Shape:
    """Normalized shape of a schema; nested schemas stay raw until they are compared."""

    types: frozenset[str]
    nullable: bool
    properties: dict[str, JsonObject]
    required: frozenset[str]
    items: JsonObject | None
    additional: JsonObject | bool | None
    enum: frozenset[str] | None
    variants: tuple[JsonObject, ...]
    fmt: str
    name: str
    title: str

    @property
    def is_any(self) -> bool:
        """The schema constrains nothing (`{}` or only a description)."""
        return not self.types and not self.variants and self.enum is None

    @property
    def label(self) -> str:
        """Name for matching variants: the title, the component name or the set of types.

        The title comes first: Pydantic names a response component `Item-Output` when the
        input and output schemas differ, while the title stays `Item`.
        """
        return self.title or self.name or ",".join(sorted(self.types)) or "any"


class SchemaDocument:
    """An OpenAPI document in which references are resolved and schema shapes are built."""

    def __init__(self, document: JsonObject) -> None:
        """The document is read lazily: references are resolved as the comparison needs them."""
        self._document = document

    def resolve(self, schema: JsonObject) -> tuple[JsonObject, str]:
        """Follow the `$ref` chain; return the target schema and the component name."""
        name = ""
        current = schema
        for _ in range(MAX_REF_CHAIN):
            reference = optional_str(current.get("$ref"))
            if not reference:
                return current, name
            name = reference.rsplit("/", 1)[-1]
            current = self._follow(reference)
        raise ContractInputError(f"$ref chain longer than {MAX_REF_CHAIN} at {name}")

    def _follow(self, reference: str) -> JsonObject:
        """Follow a local JSON Pointer inside the document."""
        if not reference.startswith(REF_PREFIX):
            raise ContractInputError(f"only local references are supported: {reference}")
        node: Json = self._document
        for token in reference.removeprefix(REF_PREFIX).split("/"):
            key = token.replace("~1", "/").replace("~0", "~")
            if not isinstance(node, dict) or key not in node:
                raise ContractInputError(f"unresolvable reference: {reference}")
            node = node[key]
        if not isinstance(node, dict):
            raise ContractInputError(f"reference does not point to a schema: {reference}")
        return node

    def shape(self, schema: JsonObject) -> Shape:
        """Build the normalized shape of a schema."""
        resolved, name = self.resolve(schema)
        merged = self._merge_all_of(resolved)
        nullable, variants = self._split_null(merged)
        if len(variants) == 1 and not _has_own_constraints(merged):
            inner = self.shape(variants[0])
            return replace(
                inner,
                nullable=inner.nullable or nullable,
                name=inner.name or name,
                title=inner.title or optional_str(merged.get("title")),
            )
        types, type_nullable = _declared_types(merged)
        if len(variants) > 1:
            types = types | frozenset().union(*(self.shape(item).types for item in variants))
        enum = _enum_values(merged)
        return Shape(
            types=types,
            nullable=nullable or type_nullable or (enum is not None and "null" in enum),
            properties={
                key: optional_object(value)
                for key, value in optional_object(merged.get("properties")).items()
            },
            required=frozenset(str_list(merged.get("required"), "required")),
            items=optional_object(merged["items"]) if "items" in merged else None,
            additional=_additional(merged.get("additionalProperties")),
            enum=None if enum is None else enum - {"null"},
            variants=tuple(variants) if len(variants) > 1 else (),
            fmt=optional_str(merged.get("format")),
            name=name,
            title=optional_str(merged.get("title")),
        )

    def _split_null(self, schema: JsonObject) -> tuple[bool, list[JsonObject]]:
        """Separate the `null` variant from the other anyOf/oneOf variants."""
        nullable = False
        variants: list[JsonObject] = []
        for raw in optional_list(schema.get("anyOf")) + optional_list(schema.get("oneOf")):
            variant = optional_object(raw)
            if self.resolve(variant)[0].get("type") == "null":
                nullable = True
            else:
                variants.append(variant)
        return nullable, variants

    def _merge_all_of(self, schema: JsonObject) -> JsonObject:
        """Merge the `allOf` members into one schema, combining properties and required fields."""
        members = optional_list(schema.get("allOf"))
        if not members:
            return schema
        merged: JsonObject = {key: value for key, value in schema.items() if key != "allOf"}
        properties = dict(optional_object(merged.get("properties")))
        required = set(str_list(merged.get("required"), "required"))
        for raw in members:
            member = self._merge_all_of(self.resolve(optional_object(raw))[0])
            properties.update(optional_object(member.get("properties")))
            required.update(str_list(member.get("required"), "required"))
            for key, value in member.items():
                if key not in {"properties", "required"}:
                    merged.setdefault(key, value)
        if properties:
            merged["properties"] = properties
        if required:
            required_names: list[Json] = [*sorted(required)]
            merged["required"] = required_names
        return merged


def _has_own_constraints(schema: JsonObject) -> bool:
    """The schema has constraints besides anyOf/oneOf (then it does not reduce to a variant)."""
    return any(key in schema for key in ("type", "properties", "items", "enum", "const"))


def _declared_types(schema: JsonObject) -> tuple[frozenset[str], bool]:
    """Types from `type` (a string or a list), with inference from `properties`/`items`."""
    raw = schema.get("type")
    declared = {raw} if isinstance(raw, str) else set(str_list(raw, "type"))
    nullable = "null" in declared
    declared.discard("null")
    if not declared and "properties" in schema:
        declared.add("object")
    if not declared and "items" in schema:
        declared.add("array")
    return frozenset(declared), nullable


def _enum_values(schema: JsonObject) -> frozenset[str] | None:
    """`enum`/`const` values in canonical JSON form, so that 1 and "1" stay distinct."""
    if "const" in schema:
        return frozenset({json.dumps(schema["const"], sort_keys=True)})
    if "enum" in schema:
        return frozenset(
            json.dumps(value, sort_keys=True) for value in optional_list(schema["enum"])
        )
    return None


def _additional(value: Json) -> JsonObject | bool | None:
    """`additionalProperties`: the schema of map values, a boolean ban or permission, or unset."""
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        return value
    return None

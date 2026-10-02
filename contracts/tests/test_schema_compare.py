"""Schema comparison rules: a request accepts the old shape, a response returns a readable one."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from whisperer_contracts.jsonvalue import Json, JsonObject
from whisperer_contracts.schema_compare import DocumentPair
from whisperer_contracts.schema_rules import Direction
from whisperer_contracts.schema_shape import SchemaDocument

REQUEST = Direction.REQUEST
RESPONSE = Direction.RESPONSE


def rules(
    draft: JsonObject,
    candidate: JsonObject,
    direction: Direction,
    draft_components: JsonObject | None = None,
    candidate_components: JsonObject | None = None,
) -> list[str]:
    pair = DocumentPair(
        SchemaDocument({"components": {"schemas": draft_components or {}}}),
        SchemaDocument({"components": {"schemas": candidate_components or {}}}),
    )
    return [
        f"{item.rule}@{item.pointer}" for item in pair.compare(draft, candidate, direction, "$")
    ]


def obj(required: list[str], **properties: JsonObject) -> JsonObject:
    req: list[Json] = [*required]
    props: JsonObject = {**properties}
    return {"type": "object", "properties": props, "required": req}


STRING: JsonObject = {"type": "string"}
INTEGER: JsonObject = {"type": "integer"}
NUMBER: JsonObject = {"type": "number"}
NULLABLE_STRING: JsonObject = {"anyOf": [{"type": "string"}, {"type": "null"}]}


def test_response_property_removed_breaks_only_when_required() -> None:
    draft = obj(["id"], id=STRING, title=STRING)
    assert rules(draft, obj(["id"], id=STRING), RESPONSE) == [
        "response.optional_property_removed@$.title"
    ]
    assert rules(draft, obj([], title=STRING), RESPONSE) == ["response.property_removed@$.id"]


def test_response_new_property_is_additive() -> None:
    assert rules(obj(["id"], id=STRING), obj(["id"], id=STRING, extra=STRING), RESPONSE) == []


def test_request_newly_required_property_breaks() -> None:
    draft = obj(["text"], text=STRING)
    assert rules(draft, obj(["text", "lang"], text=STRING, lang=STRING), REQUEST) == [
        "request.property_newly_required@$.lang"
    ]


def test_request_property_dropped_is_ignored_or_rejected() -> None:
    draft = obj([], text=STRING, lang=STRING)
    assert rules(draft, obj([], text=STRING), REQUEST) == ["request.property_ignored@$.lang"]
    forbidding = obj([], text=STRING) | {"additionalProperties": False}
    assert rules(draft, forbidding, REQUEST) == ["request.property_rejected@$.lang"]


def test_integer_and_number_widen_in_the_safe_direction_only() -> None:
    assert rules(INTEGER, NUMBER, REQUEST) == []
    assert rules(NUMBER, INTEGER, REQUEST) == ["request.type_changed@$"]
    assert rules(NUMBER, INTEGER, RESPONSE) == []
    assert rules(INTEGER, NUMBER, RESPONSE) == ["response.type_changed@$"]


def test_nullable_rules_mirror_each_other() -> None:
    assert rules(STRING, NULLABLE_STRING, RESPONSE) == ["response.became_nullable@$"]
    assert rules(NULLABLE_STRING, STRING, RESPONSE) == []
    assert rules(NULLABLE_STRING, STRING, REQUEST) == ["request.null_rejected@$"]
    assert rules(STRING, NULLABLE_STRING, REQUEST) == []


def test_enum_changes() -> None:
    draft: JsonObject = {"type": "string", "enum": ["a", "b"]}
    assert rules(draft, {"type": "string", "enum": ["a"]}, REQUEST) == [
        "request.enum_value_removed@$"
    ]
    assert rules(draft, {"type": "string", "enum": ["a", "b", "c"]}, RESPONSE) == [
        "response.enum_value_added@$"
    ]
    assert rules(draft, STRING, RESPONSE) == ["response.enum_removed@$"]
    assert rules(STRING, {"type": "string", "enum": ["a"]}, REQUEST) == [
        "request.enum_introduced@$"
    ]


def test_references_and_all_of_are_resolved_before_comparing() -> None:
    draft_components: JsonObject = {"Note": obj(["id", "body"], id=STRING, body=STRING)}
    candidate_components: JsonObject = {
        "Base": obj(["id"], id=STRING),
        "Note": {"allOf": [{"$ref": "#/components/schemas/Base"}, obj([], body=STRING)]},
    }
    found = rules(
        {"$ref": "#/components/schemas/Note"},
        {"$ref": "#/components/schemas/Note"},
        RESPONSE,
        draft_components,
        candidate_components,
    )
    assert found == ["response.property_no_longer_required@$.body"]


def test_recursive_schemas_terminate() -> None:
    tree: JsonObject = {
        "Node": obj(
            ["children"], children={"type": "array", "items": {"$ref": "#/components/schemas/Node"}}
        )
    }
    reference: JsonObject = {"$ref": "#/components/schemas/Node"}
    assert rules(reference, reference, RESPONSE, tree, tree) == []


def test_array_items_are_compared() -> None:
    draft: JsonObject = {"type": "array", "items": obj(["id"], id=STRING)}
    candidate: JsonObject = {"type": "array", "items": obj([], id=STRING)}
    assert rules(draft, candidate, RESPONSE) == ["response.property_no_longer_required@$[].id"]


def test_union_variants_are_matched_by_name() -> None:
    components: JsonObject = {
        "Text": obj(["text"], text=STRING) | {"title": "Text"},
        "Image": obj(["url"], url=STRING) | {"title": "Image"},
        "Audio": obj(["src"], src=STRING) | {"title": "Audio"},
    }
    draft: JsonObject = {
        "anyOf": [{"$ref": "#/components/schemas/Text"}, {"$ref": "#/components/schemas/Image"}]
    }
    narrowed: JsonObject = {
        "anyOf": [{"$ref": "#/components/schemas/Text"}, {"$ref": "#/components/schemas/Audio"}]
    }
    assert rules(draft, narrowed, REQUEST, components, components) == [
        "request.variant_removed@$<Image>"
    ]
    assert rules(draft, narrowed, RESPONSE, components, components) == [
        "response.variant_added@$<Audio>"
    ]


def test_variants_match_by_title_when_component_names_differ() -> None:
    draft_components: JsonObject = {"Text": obj(["text"], text=STRING) | {"title": "Text"}}
    candidate_components: JsonObject = {
        "Text-Output": obj(["text"], text=STRING) | {"title": "Text"}
    }
    union: JsonObject = {"anyOf": [{"$ref": "#/components/schemas/Text"}, INTEGER]}
    renamed: JsonObject = {"anyOf": [{"$ref": "#/components/schemas/Text-Output"}, INTEGER]}
    assert rules(union, renamed, RESPONSE, draft_components, candidate_components) == []


def test_untyped_draft_response_is_not_compared_and_untyped_candidate_is_risky() -> None:
    assert rules({}, obj(["id"], id=STRING), RESPONSE) == []
    assert rules(obj(["id"], id=STRING), {}, RESPONSE) == ["response.schema_untyped@$"]


def test_unknown_reference_is_an_input_error() -> None:
    from whisperer_contracts.jsonvalue import ContractInputError  # noqa: PLC0415

    with pytest.raises(ContractInputError, match="unresolvable reference"):
        rules({"$ref": "#/components/schemas/Missing"}, STRING, RESPONSE)


_LEAVES = st.sampled_from([STRING, INTEGER, NUMBER, NULLABLE_STRING, {"type": "boolean"}, {}])


def _array_of(item: JsonObject) -> JsonObject:
    return {"type": "array", "items": item}


def _extend(children: st.SearchStrategy[JsonObject]) -> st.SearchStrategy[JsonObject]:
    names = st.text(alphabet="abcdef", min_size=1, max_size=3)
    objects = st.dictionaries(names, children, max_size=4).flatmap(
        lambda props: st.lists(st.sampled_from(sorted(props) or ["_"]), unique=True).map(
            lambda required: obj([name for name in required if name in props], **props)
        )
    )
    arrays = children.map(_array_of)
    return objects | arrays


SCHEMAS = st.recursive(_LEAVES, _extend, max_leaves=12)


@given(SCHEMAS)
def test_any_schema_is_compatible_with_itself(schema: JsonObject) -> None:
    assert rules(schema, schema, REQUEST) == []
    assert rules(schema, schema, RESPONSE) == []

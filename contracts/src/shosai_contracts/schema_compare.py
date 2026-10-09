"""Comparison of draft and v2 schemas that takes the direction of data into account.

Request: v2 must accept everything the draft accepted, because the client sends the
old shape. Response: v2 must return only what a draft client can read, because the
client decodes the old shape. Hence the mirrored rules: a new required field breaks
a request, and a missing field breaks a response.
"""

from dataclasses import dataclass, field

from shosai_contracts.jsonvalue import JsonObject
from shosai_contracts.model import Difference
from shosai_contracts.schema_rules import Direction, schema_difference, types_covered
from shosai_contracts.schema_shape import SchemaDocument, Shape

MAX_DEPTH = 40


@dataclass(frozen=True, slots=True)
class DocumentPair:
    """The draft and v2 OpenAPI documents in which schema references are resolved."""

    draft: SchemaDocument
    candidate: SchemaDocument

    def compare(
        self,
        draft_schema: JsonObject,
        candidate_schema: JsonObject,
        direction: Direction,
        pointer: str,
    ) -> list[Difference]:
        """Every difference between a pair of schemas in the given direction."""
        comparison = _Comparison(self, direction)
        comparison.compare(draft_schema, candidate_schema, pointer, 0)
        return comparison.differences


@dataclass(slots=True)
class _Comparison:
    """One comparison; it accumulates differences and guards against reference cycles."""

    documents: DocumentPair
    direction: Direction
    differences: list[Difference] = field(default_factory=list)
    seen: set[tuple[str, str]] = field(default_factory=set)

    def report(self, rule: str, pointer: str, **values: str) -> None:
        self.differences.append(schema_difference(f"{self.direction}.{rule}", pointer, **values))

    def compare(
        self, draft_raw: JsonObject, cand_raw: JsonObject, pointer: str, depth: int
    ) -> None:
        if depth > MAX_DEPTH:
            return
        draft = self.documents.draft.shape(draft_raw)
        cand = self.documents.candidate.shape(cand_raw)
        if draft.name and cand.name:
            # Пара компонентов сравнивается один раз: так рекурсивные схемы конечны.
            if (draft.name, cand.name) in self.seen:
                return
            self.seen.add((draft.name, cand.name))
        self.compare_shapes(draft, cand, pointer, depth)

    def compare_shapes(self, draft: Shape, cand: Shape, pointer: str, depth: int) -> None:
        if self.direction is Direction.REQUEST:
            self.request(draft, cand, pointer, depth)
        else:
            self.response(draft, cand, pointer, depth)

    def request(self, draft: Shape, cand: Shape, pointer: str, depth: int) -> None:
        """v2 must accept any value that the draft schema allows."""
        if cand.is_any:
            return
        if draft.is_any:
            self.report("schema_constrained", pointer)
            return
        if not types_covered(draft.types, cand.types):
            self.report("type_changed", pointer, draft=_types(draft), candidate=_types(cand))
            return
        if draft.nullable and not cand.nullable:
            self.report("null_rejected", pointer)
        if cand.enum is not None and draft.enum is None:
            self.report("enum_introduced", pointer, values=_values(cand.enum))
        elif cand.enum is not None and draft.enum is not None and draft.enum - cand.enum:
            self.report("enum_value_removed", pointer, values=_values(draft.enum - cand.enum))
        self.format(draft, cand, pointer)
        if draft.variants or cand.variants:
            self.variants(draft, cand, pointer, depth)
            return
        self.request_object(draft, cand, pointer, depth)
        self.items(draft, cand, pointer, depth)

    def response(self, draft: Shape, cand: Shape, pointer: str, depth: int) -> None:
        """v2 must return only values that a draft client can read."""
        if draft.is_any:
            return
        if cand.is_any:
            self.report("schema_untyped", pointer)
            return
        if not types_covered(cand.types, draft.types):
            self.report("type_changed", pointer, draft=_types(draft), candidate=_types(cand))
            return
        if cand.nullable and not draft.nullable:
            self.report("became_nullable", pointer)
        if draft.enum is not None and cand.enum is None:
            self.report("enum_removed", pointer, values=_values(draft.enum))
        elif draft.enum is not None and cand.enum is not None and cand.enum - draft.enum:
            self.report("enum_value_added", pointer, values=_values(cand.enum - draft.enum))
        self.format(draft, cand, pointer)
        if draft.variants or cand.variants:
            self.variants(draft, cand, pointer, depth)
            return
        self.response_object(draft, cand, pointer, depth)
        self.items(draft, cand, pointer, depth)

    def format(self, draft: Shape, cand: Shape, pointer: str) -> None:
        if draft.fmt and cand.fmt != draft.fmt:
            self.report(
                "format_changed", pointer, draft=repr(draft.fmt), candidate=repr(cand.fmt or "none")
            )

    def request_object(self, draft: Shape, cand: Shape, pointer: str, depth: int) -> None:
        for name in sorted(cand.required - draft.required):
            self.report("property_newly_required", f"{pointer}.{name}", name=name)
        for name, draft_property in sorted(draft.properties.items()):
            cand_property = cand.properties.get(name)
            if cand_property is not None:
                self.compare(draft_property, cand_property, f"{pointer}.{name}", depth + 1)
            elif cand.additional is False:
                self.report("property_rejected", f"{pointer}.{name}", name=name)
            else:
                self.report("property_ignored", f"{pointer}.{name}", name=name)
        if isinstance(draft.additional, dict) and isinstance(cand.additional, dict):
            self.compare(draft.additional, cand.additional, f"{pointer}{{*}}", depth + 1)
        elif draft.additional not in (None, False) and cand.additional is False:
            self.report("additional_properties_rejected", pointer)

    def response_object(self, draft: Shape, cand: Shape, pointer: str, depth: int) -> None:
        for name, draft_property in sorted(draft.properties.items()):
            cand_property = cand.properties.get(name)
            required = name in draft.required
            if cand_property is None:
                rule = "property_removed" if required else "optional_property_removed"
                self.report(rule, f"{pointer}.{name}", name=name)
                continue
            if required and name not in cand.required:
                self.report("property_no_longer_required", f"{pointer}.{name}", name=name)
            self.compare(draft_property, cand_property, f"{pointer}.{name}", depth + 1)
        if isinstance(draft.additional, dict) and isinstance(cand.additional, dict):
            self.compare(draft.additional, cand.additional, f"{pointer}{{*}}", depth + 1)

    def items(self, draft: Shape, cand: Shape, pointer: str, depth: int) -> None:
        if draft.items is not None and cand.items is not None:
            self.compare(draft.items, cand.items, f"{pointer}[]", depth + 1)

    def variants(self, draft: Shape, cand: Shape, pointer: str, depth: int) -> None:
        """Unions are matched by variant name (component or title).

        Request: v2 must accept every draft variant. Response: every v2 variant must be
        known to a draft client. If the other side is not a union, the variant is compared
        with it as a whole.
        """
        request = self.direction is Direction.REQUEST
        documents = self.documents
        source_document = documents.draft if request else documents.candidate
        target_document = documents.candidate if request else documents.draft
        source, target = (draft, cand) if request else (cand, draft)
        targets = {target_document.shape(item).label: item for item in target.variants}
        for raw in source.variants:
            shape = source_document.shape(raw)
            at = f"{pointer}<{shape.label}>"
            match = targets.get(shape.label)
            if not targets:
                pair = (shape, target) if request else (target, shape)
                self.compare_shapes(*pair, at, depth + 1)
            elif match is not None:
                self.compare(*((raw, match) if request else (match, raw)), at, depth + 1)
            else:
                self.report("variant_removed" if request else "variant_added", at, name=shape.label)


def _types(shape: Shape) -> str:
    return "|".join(sorted(shape.types)) or "any"


def _values(values: frozenset[str]) -> str:
    return ", ".join(sorted(values))

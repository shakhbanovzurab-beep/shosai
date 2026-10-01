"""Нормализация JSON Schema из OpenAPI 3.1 в плоскую «форму» для сравнения.

FastAPI и Pydantic пишут одну и ту же форму данных по-разному: `$ref` на
компонент, `allOf` из одного элемента, `anyOf [X, null]` вместо nullable,
`type` строкой или списком. Сравнивать сырые схемы значило бы ловить эти
различия записи вместо различий контракта, поэтому схема сначала сводится к
`Shape`: набор типов, nullable, свойства, элементы массива, перечисление,
варианты объединения.
"""

import json
from dataclasses import dataclass, replace

from whisperer_contracts.jsonvalue import (
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
    """Нормализованная форма схемы; вложенные схемы остаются сырыми до сравнения."""

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
        """Схема ничего не ограничивает (`{}` или только описание)."""
        return not self.types and not self.variants and self.enum is None

    @property
    def label(self) -> str:
        """Имя для сопоставления вариантов: заголовок, имя компонента или набор типов.

        Заголовок идёт первым: Pydantic называет компонент ответа `Item-Output`,
        когда схемы ввода и вывода различаются, а заголовок остаётся `Item`.
        """
        return self.title or self.name or ",".join(sorted(self.types)) or "any"


class SchemaDocument:
    """Документ OpenAPI, в котором разрешаются ссылки и строятся формы схем."""

    def __init__(self, document: JsonObject) -> None:
        """Документ разбирается лениво: ссылки разрешаются по мере сравнения."""
        self._document = document

    def resolve(self, schema: JsonObject) -> tuple[JsonObject, str]:
        """Проходит цепочку `$ref`; возвращает целевую схему и имя компонента."""
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
        """Переходит по локальному JSON Pointer внутри документа."""
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
        """Строит нормализованную форму схемы."""
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
        """Отделяет вариант `null` от остальных вариантов anyOf/oneOf."""
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
        """Сливает члены `allOf` в одну схему: свойства и обязательные поля объединяются."""
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
    """У схемы есть ограничения помимо anyOf/oneOf (тогда она не сводится к варианту)."""
    return any(key in schema for key in ("type", "properties", "items", "enum", "const"))


def _declared_types(schema: JsonObject) -> tuple[frozenset[str], bool]:
    """Типы из `type` (строка или список) с выводом из `properties`/`items`."""
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
    """Значения `enum`/`const` в каноническом JSON-виде, чтобы 1 и "1" различались."""
    if "const" in schema:
        return frozenset({json.dumps(schema["const"], sort_keys=True)})
    if "enum" in schema:
        return frozenset(
            json.dumps(value, sort_keys=True) for value in optional_list(schema["enum"])
        )
    return None


def _additional(value: Json) -> JsonObject | bool | None:
    """`additionalProperties`: схема значений словаря, запрет/разрешение или не задано."""
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        return value
    return None

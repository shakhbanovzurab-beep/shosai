"""Catalogue of schema comparison rules: the impact and text of each difference.

The rules live in one place so that the README and the report refer to the same
names and the comparison code does not repeat the wording.
"""

from enum import StrEnum

from shosai_contracts.model import Difference, Impact


class Direction(StrEnum):
    """Who writes the data: the client (request) or the server (response)."""

    REQUEST = "request"
    RESPONSE = "response"


def types_covered(inner: frozenset[str], outer: frozenset[str]) -> bool:
    """Every type in `inner` is allowed in `outer`; an integer is a special case of a number."""
    return all(kind in outer or (kind == "integer" and "number" in outer) for kind in inner)


SCHEMA_RULES: dict[str, tuple[Impact, str]] = {
    "request.schema_constrained": (
        Impact.RISKY,
        "draft accepted any value here; v2 now constrains it",
    ),
    "request.type_changed": (Impact.BREAKING, "draft clients send {draft}; v2 accepts {candidate}"),
    "request.null_rejected": (Impact.BREAKING, "draft clients may send null; v2 rejects null"),
    "request.enum_introduced": (Impact.RISKY, "v2 restricts the value to {values}"),
    "request.enum_value_removed": (Impact.BREAKING, "v2 no longer accepts {values}"),
    "request.format_changed": (Impact.RISKY, "format changed from {draft} to {candidate}"),
    "request.property_newly_required": (
        Impact.BREAKING,
        "v2 requires '{name}', which draft clients may omit",
    ),
    "request.property_rejected": (
        Impact.BREAKING,
        "draft clients send '{name}'; v2 forbids unknown properties",
    ),
    "request.property_ignored": (
        Impact.RISKY,
        "draft clients send '{name}'; v2 no longer reads it",
    ),
    "request.additional_properties_rejected": (
        Impact.BREAKING,
        "draft accepted arbitrary keys; v2 forbids them",
    ),
    "request.variant_removed": (Impact.BREAKING, "v2 no longer accepts variant '{name}'"),
    "response.schema_untyped": (
        Impact.RISKY,
        "draft declared a typed value here; v2 declares none, so it cannot be verified",
    ),
    "response.type_changed": (
        Impact.BREAKING,
        "draft clients decode {draft}; v2 returns {candidate}",
    ),
    "response.became_nullable": (
        Impact.BREAKING,
        "v2 may return null where draft clients expect a value",
    ),
    "response.enum_removed": (
        Impact.RISKY,
        "draft clients expect one of {values}; v2 does not restrict it",
    ),
    "response.enum_value_added": (Impact.RISKY, "v2 may return {values}, unknown to draft clients"),
    "response.format_changed": (Impact.RISKY, "format changed from {draft} to {candidate}"),
    "response.property_removed": (
        Impact.BREAKING,
        "draft clients read '{name}'; v2 no longer returns it",
    ),
    "response.optional_property_removed": (
        Impact.RISKY,
        "draft clients read '{name}' when present; v2 no longer returns it",
    ),
    "response.property_no_longer_required": (
        Impact.BREAKING,
        "draft clients rely on '{name}' always being present",
    ),
    "response.variant_added": (
        Impact.RISKY,
        "v2 may return variant '{name}', unknown to draft clients",
    ),
}


def schema_difference(rule: str, pointer: str, **values: str) -> Difference:
    """A difference under a catalogue rule; an unknown rule is a programming error."""
    impact, template = SCHEMA_RULES[rule]
    return Difference(rule, impact, pointer, template.format(**values))

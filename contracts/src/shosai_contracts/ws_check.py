"""Comparison of a draft WebSocket endpoint with the v2 endpoint using the frame catalogues.

A client frame is compared as a request (v2 must accept it), a server frame as a
response (v2 must send what a draft client can read). New server frame types are
allowed: under the §10 rule clients ignore unknown ones.
"""

from shosai_contracts.model import CompatClass, Difference, Impact
from shosai_contracts.schema_rules import types_covered
from shosai_contracts.ws_catalogue import (
    CloseCode,
    Endpoint,
    Frame,
    FrameDirection,
    FrameField,
)


def frame_subject(endpoint_path: str, frame: Frame) -> str:
    """Label of a frame in the report: `WS <path> client:<type>` or `server:<type>`."""
    side = "client" if frame.direction is FrameDirection.CLIENT_TO_SERVER else "server"
    return f"WS {endpoint_path} {side}:{frame.frame_type}"


def compare_connection(draft: Endpoint, candidate: Endpoint) -> list[Difference]:
    """The connection: discriminator, authentication mechanisms, parameters, close codes."""
    differences: list[Difference] = []
    if draft.discriminator != candidate.discriminator:
        differences.append(
            Difference(
                "ws.discriminator_changed",
                Impact.BREAKING,
                "discriminator",
                f"draft frames are told apart by {draft.discriminator or 'none'!r}; "
                f"v2 uses {candidate.discriminator or 'none'!r}",
            )
        )
    for mechanism in sorted(draft.auth - candidate.auth):
        differences.append(
            Difference(
                "ws.auth_mechanism_removed",
                Impact.BREAKING,
                f"auth.{mechanism}",
                f"draft clients authenticate with {mechanism!r}; v2 does not support it",
            )
        )
    differences += compare_fields(
        draft.query_params, candidate.query_params, FrameDirection.CLIENT_TO_SERVER, "query"
    )
    differences += _compare_codes(
        draft.close_codes, candidate.close_codes, "ws.close_code_removed", "close", "closes with"
    )
    differences += _compare_codes(
        draft.handshake_rejections,
        candidate.handshake_rejections,
        "ws.handshake_status_removed",
        "handshake",
        "rejects the handshake with HTTP",
    )
    return differences


def _compare_codes(
    draft: tuple[CloseCode, ...],
    candidate: tuple[CloseCode, ...],
    rule: str,
    prefix: str,
    action: str,
) -> list[Difference]:
    """Every draft code must occur in v2; strictly so for a code that clients react to."""
    present = {item.code for item in candidate}
    handled = {item.code for item in draft if item.handled_by_clients}
    return [
        Difference(
            rule,
            Impact.BREAKING if code in handled else Impact.RISKY,
            f"{prefix}.{code}",
            f"draft {action} {code}"
            + ("; shipped clients react to it" if code in handled else "")
            + "; v2 never does",
        )
        for code in sorted({item.code for item in draft} - present)
    ]


def compare_frame(draft: Frame, candidate: Frame | None) -> list[Difference]:
    """A v2 frame against the draft frame; a missing frame is an incompatibility."""
    if candidate is None:
        rule, message = (
            ("ws.frame_not_accepted", "v2 does not accept this frame from draft clients")
            if draft.direction is FrameDirection.CLIENT_TO_SERVER
            else ("ws.frame_not_sent", "v2 never sends this frame; draft clients rely on it")
        )
        return [Difference(rule, Impact.BREAKING, "", message)]
    differences: list[Difference] = []
    if draft.encoding is not candidate.encoding:
        differences.append(
            Difference(
                "ws.frame_encoding_changed",
                Impact.BREAKING,
                "encoding",
                f"encoding changed from {draft.encoding} to {candidate.encoding}",
            )
        )
    if draft.binary_format != candidate.binary_format:
        differences.append(
            Difference(
                "ws.binary_format_changed",
                Impact.BREAKING,
                "binary_format",
                f"binary layout changed from {draft.binary_format!r} "
                f"to {candidate.binary_format!r}",
            )
        )
    differences += compare_fields(draft.fields, candidate.fields, draft.direction, "")
    return differences


def compare_fields(
    draft: tuple[FrameField, ...],
    candidate: tuple[FrameField, ...],
    direction: FrameDirection,
    prefix: str,
) -> list[Difference]:
    """Frame fields or connection parameters, compared in the direction of the data."""
    draft_fields = {field.name: field for field in draft}
    candidate_fields = {field.name: field for field in candidate}
    if direction is FrameDirection.CLIENT_TO_SERVER:
        return _client_fields(draft_fields, candidate_fields, prefix)
    return _server_fields(draft_fields, candidate_fields, prefix)


def _pointer(prefix: str, name: str) -> str:
    return f"{prefix}.{name}" if prefix else name


def _client_fields(
    draft: dict[str, FrameField], candidate: dict[str, FrameField], prefix: str
) -> list[Difference]:
    """The client sends the old shape: v2 must accept it."""
    differences: list[Difference] = []
    for name, field in sorted(candidate.items()):
        previous = draft.get(name)
        if field.required and (previous is None or not previous.required):
            differences.append(
                Difference(
                    "ws.field_newly_required",
                    Impact.BREAKING,
                    _pointer(prefix, name),
                    f"v2 requires '{name}', which draft clients may omit",
                )
            )
    for name, field in sorted(draft.items()):
        current = candidate.get(name)
        if current is None:
            differences.append(
                Difference(
                    "ws.field_ignored",
                    Impact.RISKY,
                    _pointer(prefix, name),
                    f"draft clients send '{name}'; v2 no longer reads it",
                )
            )
        elif current.types and not types_covered(field.types, current.types):
            differences.append(
                Difference(
                    "ws.field_type_changed",
                    Impact.BREAKING,
                    _pointer(prefix, name),
                    f"draft clients send {_types(field)}; v2 accepts {_types(current)}",
                )
            )
    return differences


def _server_fields(
    draft: dict[str, FrameField], candidate: dict[str, FrameField], prefix: str
) -> list[Difference]:
    """The client reads the old shape: v2 must keep sending it."""
    differences: list[Difference] = []
    for name, field in sorted(draft.items()):
        current = candidate.get(name)
        pointer = _pointer(prefix, name)
        if current is None:
            differences.append(
                Difference(
                    "ws.field_removed" if field.required else "ws.optional_field_removed",
                    Impact.BREAKING if field.required else Impact.RISKY,
                    pointer,
                    f"draft clients read '{name}'; v2 no longer sends it",
                )
            )
            continue
        if field.required and not current.required:
            differences.append(
                Difference(
                    "ws.field_no_longer_required",
                    Impact.BREAKING,
                    pointer,
                    f"draft clients rely on '{name}' always being present",
                )
            )
        if not field.types:
            continue
        if not current.types:
            differences.append(
                Difference(
                    "ws.field_untyped",
                    Impact.RISKY,
                    pointer,
                    f"draft sends {_types(field)}; v2 declares no type, so it cannot be verified",
                )
            )
        elif not types_covered(current.types, field.types):
            differences.append(
                Difference(
                    "ws.field_type_changed",
                    Impact.BREAKING,
                    pointer,
                    f"draft clients decode {_types(field)}; v2 sends {_types(current)}",
                )
            )
    return differences


def frame_class(endpoint: Endpoint, frame: Frame) -> CompatClass:
    """The frame's class; a frame without an explicit class is protected like its endpoint."""
    return frame.compat_class or endpoint.compat_class or CompatClass.UNUSED


def _types(field: FrameField) -> str:
    return "|".join(sorted(field.types)) or "any"

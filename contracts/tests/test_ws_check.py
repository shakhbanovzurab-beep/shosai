"""Каталог WebSocket: разбор формата и правила сравнения кадров и подключения."""

import pytest

from whisperer_contracts.jsonvalue import ContractInputError, Json, JsonObject, as_list, as_object
from whisperer_contracts.ws_catalogue import CATALOGUE_FORMAT, Endpoint, parse_catalogue
from whisperer_contracts.ws_check import compare_connection, compare_frame


def endpoint(**overrides: Json) -> JsonObject:
    base: JsonObject = {
        "path": "/v1/ws/realtime",
        "discriminator": "type",
        "auth": ["header:authorization-bearer", "subprotocol:whisperer-bearer"],
        "query_params": [],
        "close_codes": [{"code": 1008}, {"code": 1012}],
        "handshake_rejections": [{"status": 403, "consumers": [{"client": "macos"}]}],
        "frames": [
            {
                "direction": "client_to_server",
                "type": "hello",
                "encoding": "json",
                "fields": [
                    {"name": "type", "type": "string", "required": True},
                    {"name": "language", "type": "string", "required": False},
                ],
            },
            {
                "direction": "server_to_client",
                "type": "transcript",
                "encoding": "json",
                "fields": [
                    {"name": "type", "type": "string", "required": True},
                    {"name": "seq", "type": "integer", "required": True},
                    {"name": "speaker", "type": "string|null", "required": False},
                ],
            },
            {
                "direction": "client_to_server",
                "type": "<binary:audio>",
                "encoding": "binary",
                "binary_format": "u8 speaker + WAV",
            },
        ],
    }
    return base | overrides


def parse(*endpoints: JsonObject) -> tuple[Endpoint, ...]:
    return parse_catalogue({"format": CATALOGUE_FORMAT, "endpoints": [*endpoints]}, "test")


def frames(item: JsonObject, *replacements: JsonObject) -> JsonObject:
    replaced = {new["type"] for new in replacements}
    keep = [
        frame
        for frame in as_list(item["frames"], "frames")
        if as_object(frame, "frame")["type"] not in replaced
    ]
    return item | {"frames": [*keep, *replacements]}


def diff(draft: JsonObject, candidate: JsonObject) -> list[str]:
    (old,), (new,) = parse(draft), parse(candidate)
    found = [f"{item.rule}@{item.pointer}" for item in compare_connection(old, new)]
    current = {frame.key: frame for frame in new.frames}
    for frame in old.frames:
        found += [
            f"{item.rule}@{frame.frame_type}.{item.pointer}"
            for item in compare_frame(frame, current.get(frame.key))
        ]
    return found


def test_identical_catalogues_are_compatible() -> None:
    assert diff(endpoint(), endpoint()) == []


def test_missing_frames_break_in_both_directions() -> None:
    base = endpoint()
    candidate = base | {"frames": []}
    assert diff(base, candidate) == [
        "ws.frame_not_accepted@hello.",
        "ws.frame_not_sent@transcript.",
        "ws.frame_not_accepted@<binary:audio>.",
    ]


def test_server_frame_field_rules() -> None:
    base = endpoint()
    candidate = frames(
        base,
        {
            "direction": "server_to_client",
            "type": "transcript",
            "encoding": "json",
            "fields": [
                {"name": "type", "type": "string", "required": True},
                {"name": "seq", "type": "string", "required": False},
            ],
        },
    )
    assert diff(base, candidate) == [
        "ws.field_no_longer_required@transcript.seq",
        "ws.field_type_changed@transcript.seq",
        "ws.optional_field_removed@transcript.speaker",
    ]


def test_client_frame_field_rules() -> None:
    base = endpoint()
    candidate = frames(
        base,
        {
            "direction": "client_to_server",
            "type": "hello",
            "encoding": "json",
            "fields": [
                {"name": "type", "type": "string", "required": True},
                {"name": "protocol", "type": "integer", "required": True},
            ],
        },
    )
    assert diff(base, candidate) == [
        "ws.field_newly_required@hello.protocol",
        "ws.field_ignored@hello.language",
    ]


def test_connection_rules() -> None:
    base = endpoint()
    candidate = endpoint(
        discriminator="t",
        auth=["header:authorization-bearer"],
        close_codes=[{"code": 1012}],
        handshake_rejections=[],
    )
    assert diff(base, candidate) == [
        "ws.discriminator_changed@discriminator",
        "ws.auth_mechanism_removed@auth.subprotocol:whisperer-bearer",
        "ws.close_code_removed@close.1008",
        "ws.handshake_status_removed@handshake.403",
    ]
    (old,), (new,) = parse(base), parse(candidate)
    impacts = {item.rule: item.impact.value for item in compare_connection(old, new)}
    assert impacts["ws.close_code_removed"] == "risky"
    assert impacts["ws.handshake_status_removed"] == "breaking"


def test_binary_layout_change_breaks() -> None:
    base = endpoint()
    candidate = frames(
        base,
        {
            "direction": "client_to_server",
            "type": "<binary:audio>",
            "encoding": "binary",
            "binary_format": "u8 speaker + raw PCM",
        },
    )
    assert diff(base, candidate) == ["ws.binary_format_changed@<binary:audio>.binary_format"]


@pytest.mark.parametrize(
    ("document", "message"),
    [
        ({"format": "other", "endpoints": []}, "format must be"),
        (
            {"format": CATALOGUE_FORMAT, "endpoints": [endpoint(), endpoint()]},
            "duplicate endpoint paths",
        ),
        (
            {
                "format": CATALOGUE_FORMAT,
                "endpoints": [
                    endpoint(
                        frames=[{"direction": "client_to_server", "type": "a", "encoding": "json"}]
                        * 2
                    )
                ],
            },
            "duplicate frames",
        ),
        (
            {
                "format": CATALOGUE_FORMAT,
                "endpoints": [
                    endpoint(
                        frames=[
                            {
                                "direction": "client_to_server",
                                "type": "a",
                                "encoding": "json",
                                "fields": [{"name": "x", "type": "uuid"}],
                            }
                        ]
                    )
                ],
            },
            "unknown type",
        ),
        (
            {
                "format": CATALOGUE_FORMAT,
                "endpoints": [
                    endpoint(frames=[{"direction": "sideways", "type": "a", "encoding": "json"}])
                ],
            },
            "sideways",
        ),
    ],
)
def test_invalid_catalogues_are_rejected(document: JsonObject, message: str) -> None:
    with pytest.raises(ContractInputError, match=message):
        parse_catalogue(document, "test")

"""OpenRouter's zero-data-retention list read strictly: off its shape is "no" (ADR 0069)."""

import httpx
import pytest

from shosai.core.ai.adapters.openrouter_endpoints import (
    keeps_nothing,
    listed_endpoints,
    model_tags,
    zero_retention,
)

JEV = "typesafe/jev-1.13"


def test_the_list_is_read_as_model_and_tag_pairs() -> None:
    document = {
        "data": [
            {"model_id": JEV, "tag": "typesafe", "name": "TypeSafe | x"},
            {"model_id": "google/gemini-3.8-flash", "tag": "google-vertex/us"},
            {"model_id": 7, "tag": "broken"},
            "not an endpoint",
        ]
    }

    assert listed_endpoints(document) == {
        (JEV, "typesafe"),
        ("google/gemini-3.8-flash", "google-vertex/us"),
    }
    assert listed_endpoints({"data": "x"}) == frozenset()
    assert listed_endpoints([]) == frozenset()


@pytest.mark.parametrize(
    "document",
    [
        {"data": {"endpoints": [{"tag": "typesafe"}, {"name": "no tag"}]}},
        {"data": {"endpoints": "typesafe"}},
        {"data": []},
        {"error": {"code": 404}},
    ],
)
def test_a_models_endpoints_out_of_shape_are_unknown(document: object) -> None:
    assert model_tags(document) is None
    assert not keeps_nothing(JEV, model_tags(document), frozenset({(JEV, "typesafe")}))


def test_every_endpoint_must_be_listed() -> None:
    listed = frozenset({(JEV, "typesafe")})

    assert keeps_nothing(JEV, ("typesafe",), listed)
    assert not keeps_nothing(JEV, ("typesafe", "other"), listed)
    assert not keeps_nothing(JEV, (), listed)


async def test_both_public_lists_are_read_without_a_key() -> None:
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/endpoints/zdr"):
            return httpx.Response(200, json={"data": [{"model_id": JEV, "tag": "typesafe"}]})
        return httpx.Response(200, json={"data": {"id": JEV, "endpoints": [{"tag": "typesafe"}]}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as client:
        assert await zero_retention(client, JEV)

    assert [str(request.url) for request in seen] == [
        "https://openrouter.ai/api/v1/endpoints/zdr",
        f"https://openrouter.ai/api/v1/models/{JEV}/endpoints",
    ]
    assert all("authorization" not in request.headers for request in seen)


async def test_a_failed_read_raises_for_the_caller_to_keep_its_status() -> None:
    failing = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(502)))

    async with failing:
        with pytest.raises(httpx.HTTPStatusError):
            await zero_retention(failing, JEV)

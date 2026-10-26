"""OpenRouter answers are parsed strictly: anything unexpected is a provider error."""

import base64
import json
from decimal import Decimal
from pathlib import Path

import pytest

from shosai.core.ai.adapters.openrouter_wire import (
    StreamedToolCalls,
    citations_of,
    image_of,
    message_body,
    reported_cost,
    stream_chunk,
    usage_of,
)
from shosai.core.ai.calls import CallClass, CallContext, CallOrigin, PlatformAccount
from shosai.core.ai.errors import AiCallError
from shosai.core.ai.requests import ChatMessage, Role, TextPart, ToolCall
from shosai.core.ai.results import Citation, Unit
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from tests.core.ai.bench import USER_ID


def test_usage_reads_tokens_cache_and_cost() -> None:
    usage = usage_of(
        {"prompt_tokens": 10, "completion_tokens": 4, "cost": 0.0021,
         "prompt_tokens_details": {"cached_tokens": 6}}
    )  # fmt: skip

    assert (usage.input_tokens, usage.cached_tokens, usage.output_tokens) == (10, 6, 4)
    assert usage.reported_cost_usd == Decimal("0.0021")


def test_billing_units_default_to_one_when_the_answer_omits_them() -> None:
    usage = usage_of({"cost": None}, unit=Unit.IMAGE)

    assert (usage.units, usage.unit, usage.reported_cost_usd) == (Decimal(1), Unit.IMAGE, None)


@pytest.mark.parametrize("raw", [None, "", "free", -1, float("nan"), True])
def test_a_missing_or_invalid_cost_is_not_a_cost(raw: object) -> None:
    assert reported_cost(raw) is None


@pytest.mark.parametrize(
    "url",
    [
        "data:text/html;base64," + base64.b64encode(b"<script>").decode(),
        "data:image/png;base64,not-base64!",
        "https://example.com/picture.png",
        "data:image/png;base64,",
    ],
)
def test_an_image_answer_must_be_a_non_empty_image(url: str) -> None:
    with pytest.raises(AiCallError):
        image_of({"images": [{"image_url": {"url": url}}]})


@pytest.mark.parametrize("line", [": OPENROUTER PROCESSING", "", "data: [DONE]", "event: x"])
def test_stream_lines_without_data_are_skipped(line: str) -> None:
    assert stream_chunk(line) is None


@pytest.mark.parametrize("line", ['data: {"error": {"message": "overloaded"}}', "data: {broken"])
def test_an_error_or_broken_chunk_ends_the_stream_as_a_provider_error(line: str) -> None:
    with pytest.raises(AiCallError):
        stream_chunk(line)


def make_context(
    *,
    scope: TenancyScope | None = None,
    account: PlatformAccount | None = None,
    feature: str = "probe.chat",
) -> CallContext:
    """A system call with the given payer and feature."""
    return CallContext(
        effect_key="k", feature=feature, call_class=CallClass.STANDARD, origin=CallOrigin.SYSTEM,
        scope=scope, platform_account=account,
    )  # fmt: skip


def test_a_context_names_one_payer_and_a_user_for_a_scope() -> None:
    with pytest.raises(ValueError, match="либо пользователь"):
        make_context()
    with pytest.raises(ValueError, match="либо пользователь"):
        make_context(scope=TenancyScope(Home.EU, USER_ID), account=PlatformAccount.SYSTEM)
    with pytest.raises(ValueError, match="user_id"):
        make_context(scope=TenancyScope(Home.EU))
    with pytest.raises(ValueError, match="snake_case"):
        make_context(account=PlatformAccount.SYSTEM, feature="Probe Chat")
    assert make_context(account=PlatformAccount.SYSTEM).payer_scope == TenancyScope(Home.EU)


def test_streamed_tool_calls_are_assembled_from_their_pieces_in_order() -> None:
    calls = StreamedToolCalls()
    for delta in (
        {"tool_calls": [{"index": 1, "id": "b", "function": {"name": "tasks__search"}}]},
        {
            "tool_calls": [
                {"index": 0, "id": "a", "function": {"name": "notes__search", "arguments": '{"q'}}
            ]
        },
        {"tool_calls": [{"index": 0, "function": {"arguments": '": "budget"}'}}]},
        {"content": "text only"},
        {"tool_calls": "broken"},
    ):
        calls.take(delta)

    assert calls.calls() == (
        ToolCall(call_id="a", name="notes__search", arguments='{"q": "budget"}'),
        ToolCall(call_id="b", name="tasks__search", arguments="{}"),
    )
    assert StreamedToolCalls().calls() == ()


def test_a_round_of_calls_and_its_answer_are_sent_in_the_provider_shape() -> None:
    call = ToolCall(call_id="a", name="notes__search", arguments='{"query": "budget"}')
    silent = ChatMessage(Role.ASSISTANT, tool_calls=(call,))
    spoken = ChatMessage(Role.ASSISTANT, (TextPart("Looking."),), tool_calls=(call,))
    answer = ChatMessage(Role.TOOL, (TextPart('{"meetings": []}'),), tool_call_id="a")

    assert message_body(silent) == {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": "a", "type": "function",
             "function": {"name": "notes__search", "arguments": '{"query": "budget"}'}}
        ],
    }  # fmt: skip
    assert message_body(spoken)["content"] == [{"type": "text", "text": "Looking."}]
    assert message_body(answer) == {
        "role": "tool", "content": '{"meetings": []}', "tool_call_id": "a",
    }  # fmt: skip


def test_a_web_answer_cites_each_web_page_once_in_the_order_cited() -> None:
    def cited(url: object, title: object = None, content: object = None) -> object:
        return {
            "type": "url_citation",
            "url_citation": {"url": url, "title": title, "content": content},
        }

    message = {
        "annotations": [
            cited("https://a.example/news", "Launch moved", "May, not April."),
            "broken",
            {"type": "file", "file": {"name": "x"}},
            cited("javascript:alert(1)", "Bad"),
            cited("https://a.example/news", "Again"),
            cited("http://b.example/"),
            {"type": "url_citation", "url_citation": "broken"},
        ]
    }

    assert citations_of(message) == (
        Citation("https://a.example/news", "Launch moved", "May, not April."),
        Citation("http://b.example/", "http://b.example/", ""),
    )
    assert citations_of({"content": "no search"}) == ()


def test_a_recorded_exa_answer_cites_the_pages_own_addresses_with_their_passages() -> None:
    recorded = json.loads(
        (Path(__file__).parent / "recorded" / "web_search_answer.json").read_text()
    )

    pages = citations_of(recorded["choices"][0]["message"])

    assert len(pages) == len({page.url for page in pages}) == 8
    assert pages[0].url == "https://www.python.org/"
    assert pages[0].title == "Welcome to Python.org"
    assert "Python 3.15.2" in pages[0].snippet
    assert all(page.url.startswith("https://") and page.snippet for page in pages)

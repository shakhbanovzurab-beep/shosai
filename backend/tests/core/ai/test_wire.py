"""OpenRouter answers are parsed strictly: anything unexpected is a provider error."""

import base64
from decimal import Decimal

import pytest

from shosai.core.ai.adapters.openrouter_wire import image_of, reported_cost, stream_chunk, usage_of
from shosai.core.ai.calls import CallClass, CallContext, CallOrigin, PlatformAccount
from shosai.core.ai.errors import AiCallError
from shosai.core.ai.results import Unit
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

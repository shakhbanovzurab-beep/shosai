"""Leo's `web.search` (agent step 13a): one bounded model call with the provider's web search,
its pages as numbered web sources, a provider's refusal as a code the model can act on."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from shosai.core.agent_tools.bindings import ReadTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.provenance import Provenance
from shosai.core.agent_tools.results import ToolErrorCode
from shosai.core.agent_tools.sources import SourceKind, SourceRef
from shosai.core.agent_tools.spec import CostClass, ToolEffect
from shosai.core.ai.calls import CallContext, CallOrigin, ModelRef, ModelRoute, Provider
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.requests import ChatRequest, Role
from shosai.core.ai.results import ChatResult, Citation, Usage
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.agent.application.run_context import text_of
from shosai.features.agent.channels.web_tools import (
    PAGES,
    WEB_SEARCH_SPEC,
    WebSearchInput,
    web_tools,
)
from shosai.features.agent.domain.preferences import Switch
from shosai.features.agent.domain.spaces import space_of
from shosai.features.agent.infrastructure.prompts import WEB_SEARCH

ROUTE = ModelRoute(ModelRef(Provider.OPENROUTER, "probe/standard"))


@dataclass
class ScriptedSearch:
    """The provider port's chat: answers with the pages given, or refuses."""

    pages: tuple[Citation, ...] = ()
    failure: AiFailure | None = None
    calls: list[tuple[CallContext, ChatRequest]] = field(default_factory=list)

    async def chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> ChatResult:
        self.calls.append((context, request))
        if self.failure is not None:
            raise AiCallError(self.failure)
        return ChatResult("Launch moved to May.", (), "stop", route.primary, Usage(), self.pages)


def bound(ai: ScriptedSearch, route: ModelRoute | None = ROUTE) -> ReadTool[Any, Any]:
    """The toolset's one tool."""
    [tool] = web_tools(ai, lambda: route)
    assert isinstance(tool, ReadTool)
    return tool


def context() -> ToolContext:
    scope = TenancyScope(Home.RU, user_id=uuid.uuid4())
    return ToolContext(scope, uuid.uuid4(), datetime.now(UTC) + timedelta(minutes=1))


def test_the_search_is_metered_egress_behind_its_switch_and_reads_as_web() -> None:
    spec = WEB_SEARCH_SPEC

    assert (spec.effect, spec.cost_class, spec.switch) == (
        ToolEffect.EGRESS, CostClass.METERED, Switch.WEB_SEARCH.value,
    )  # fmt: skip
    assert (spec.provenance, spec.step_detail) == (Provenance.WEB, "query")


async def test_the_pages_found_become_numbered_web_sources_of_the_answer() -> None:
    long_url = "https://long.example/" + "x" * 2_100
    pages = (
        Citation("https://news.example/launch", "Launch moved", "May, " * 100),
        Citation(long_url, "Too long to cite"),
        *(Citation(f"https://site{n}.example/", "") for n in range(6)),
    )
    ai = ScriptedSearch(pages)
    call = context()

    result = await bound(ai).run(WebSearchInput(query="launch date"), call)

    assert result.output is not None
    assert result.output.answer == "Launch moved to May."
    assert len(result.output.pages) == PAGES
    first = result.sources[0]
    assert (first.kind, first.id, first.title, first.locator, first.org_id) == (
        SourceKind.WEB, "https://news.example/launch", "Launch moved", None, None,
    )  # fmt: skip
    assert first.quote is not None
    assert len(first.quote) == len(result.output.pages[0].snippet) == 300
    assert [s.title for s in result.sources[1:]] == [f"site{n}.example" for n in range(4)]
    [(sent, request)] = ai.calls
    assert (sent.feature, sent.origin, sent.scope) == (
        "agent.web_search", CallOrigin.INTERACTIVE, call.scope,
    )  # fmt: skip
    assert sent.effect_key.startswith(f"agent.web_search:{call.run_id}:")
    assert request.web_search_results == PAGES
    assert [m.role for m in request.messages] == [Role.SYSTEM, Role.USER]
    assert [text_of(m) for m in request.messages] == [WEB_SEARCH, "launch date"]


async def test_every_search_is_its_own_call() -> None:
    ai = ScriptedSearch()
    tool, call = bound(ai), context()

    await tool.run(WebSearchInput(query="one"), call)
    await tool.run(WebSearchInput(query="one"), call)

    assert len({sent.effect_key for sent, _ in ai.calls}) == 2


@pytest.mark.parametrize(
    ("failure", "code"),
    [
        (AiFailure.RATE_LIMITED, ToolErrorCode.RATE_LIMITED),
        (AiFailure.RETRY_LATER, ToolErrorCode.RATE_LIMITED),
        (AiFailure.DEADLINE_EXCEEDED, ToolErrorCode.TIMEOUT),
        (AiFailure.SPEND_LIMIT, ToolErrorCode.LIMIT_REACHED),
        (AiFailure.PROVIDER_ERROR, ToolErrorCode.UNAVAILABLE),
        (AiFailure.EXPENSIVE_PAUSED, ToolErrorCode.UNAVAILABLE),
    ],
)
async def test_a_provider_s_refusal_is_a_code_the_model_can_act_on(
    failure: AiFailure, code: ToolErrorCode
) -> None:
    result = await bound(ScriptedSearch(failure=failure)).run(
        WebSearchInput(query="launch"), context()
    )

    assert result.error is not None
    assert result.error.code == code
    assert result.sources == ()


async def test_without_a_standard_model_the_search_is_unavailable() -> None:
    ai = ScriptedSearch()

    result = await bound(ai, None).run(WebSearchInput(query="launch"), context())

    assert result.error is not None
    assert result.error.code == ToolErrorCode.UNAVAILABLE
    assert ai.calls == []


def test_a_web_page_is_listed_with_its_site_not_a_space_of_the_person_s() -> None:
    org = uuid.uuid4()
    page = SourceRef(SourceKind.WEB, "https://news.example:8443/launch?a=1", "Launch")
    task = SourceRef(SourceKind.TASK, "t1", "Book travel", org_id=org)
    own = SourceRef(SourceKind.FILE, "f1", "Plan")

    spaces = [space_of(ref, "ru", {org: "Acme"}) for ref in (page, task, own)]

    assert spaces == ["news.example", "Acme", "Личное"]

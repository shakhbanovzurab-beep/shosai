"""Leo's `web` toolset: `web.search` (Leo §8.1, §7.4; agent steps 13a, 13b).

The search runs through the provider port's own web search: a short model call reads the pages
the search found and answers from them, and each page is a source of the answer, numbered with
the others, its site as its space. Text from the web is untrusted: the result is wrapped as
`web` and raises the run's taint. The tool sends the query outside Shosai, so it is `egress`,
metered — the call's cost lands on the person's turn like the turn's own — offered only while
the person keeps "Web search" on in Settings > Leo, and, once the run has read text from
outside, a card the person approves first, worded here with the query.
"""

from collections.abc import Callable, Mapping
from datetime import timedelta
from typing import Final, Protocol
from urllib.parse import urlsplit
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from shosai.core.agent_tools.bindings import AgentTool, ReadTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.previews import PreviewField, PreviewWording
from shosai.core.agent_tools.provenance import Provenance
from shosai.core.agent_tools.results import ToolErrorCode, ToolResult
from shosai.core.agent_tools.sources import SOURCE_ID_MAX, TITLE_MAX, SourceKind, SourceRef
from shosai.core.agent_tools.spec import CostClass, ToolEffect, ToolSpec
from shosai.core.ai.calls import CallClass, CallContext, CallOrigin, ModelRoute
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.requests import ChatRequest, Role
from shosai.core.ai.results import ChatResult, Citation
from shosai.features.agent.application.run_context import text_message
from shosai.features.agent.domain.preferences import Switch
from shosai.features.agent.infrastructure.prompts import WEB_SEARCH

QUERY_MAX: Final = 300
# Страниц поиска на запрос: столько читает модель поиска и столько источников у ответа.
PAGES: Final = 5
ANSWER_TOKENS: Final = 800
SNIPPET_MAX: Final = 300
SEARCH_TIMEOUT: Final = timedelta(seconds=30)
SEARCH_FEATURE: Final = "agent.web_search"
# Отказ провайдера — код, по которому модель решает, повторять ли; прочее — «недоступно».
FAILURE_CODES: Final[Mapping[AiFailure, ToolErrorCode]] = {
    AiFailure.RATE_LIMITED: ToolErrorCode.RATE_LIMITED,
    AiFailure.RETRY_LATER: ToolErrorCode.RATE_LIMITED,
    AiFailure.DEADLINE_EXCEEDED: ToolErrorCode.TIMEOUT,
    AiFailure.SPEND_LIMIT: ToolErrorCode.LIMIT_REACHED,
}


class WebSearchInput(BaseModel):
    """What to look up on the web."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        min_length=1,
        max_length=QUERY_MAX,
        description="What to look up, as a short search query in any language.",
    )


class WebHit(BaseModel):
    """A page the search found."""

    title: str = Field(description="The page's title.")
    url: str = Field(description="The page's address.")
    snippet: str = Field(description="The passage of the page the answer used.")


class WebSearchOutput(BaseModel):
    """What the web says about the query."""

    answer: str = Field(description="An answer from the pages found; cite them as sources.")
    pages: list[WebHit] = Field(description="The pages found, in the order they are cited.")


# Карточка поиска в заражённом прогоне: что уйдёт наружу — сам запрос.
SEARCH_CARD: Final = PreviewWording(
    key="agent.web.search",
    params=("query",),
    title={
        "en": "Search the web", "fr": "Rechercher sur le Web", "de": "Im Web suchen",
        "ru": "Поискать в интернете", "nl": "Zoeken op internet", "it": "Cerca sul web",
        "es": "Buscar en la web", "pt-BR": "Pesquisar na web", "ar": "البحث في الويب",
        "tr": "İnternette ara", "ko": "웹 검색", "hi": "वेब पर खोजें", "vi": "Tìm kiếm trên web",
        "zh-Hant": "搜尋網路", "ja": "ウェブを検索", "id": "Cari di web",
    },
    fields=(
        PreviewField("query", {
            "en": "Query", "fr": "Requête", "de": "Suchanfrage", "ru": "Запрос",
            "nl": "Zoekopdracht", "it": "Ricerca", "es": "Consulta", "pt-BR": "Consulta",
            "ar": "عبارة البحث", "tr": "Arama sorgusu", "ko": "검색어", "hi": "खोज",
            "vi": "Truy vấn", "zh-Hant": "搜尋字詞", "ja": "検索語句", "id": "Kueri",
        }),
    ),
)  # fmt: skip
WEB_SEARCH_SPEC: Final = ToolSpec(
    name="web.search",
    toolset="web",
    description=(
        "Search the web for current or public information the user's Shosai does not hold: "
        "news, prices, public facts, documentation. Never put the user's private data into "
        "the query."
    ),
    input=WebSearchInput,
    output=WebSearchOutput,
    effect=ToolEffect.EGRESS,
    cost_class=CostClass.METERED,
    switch=Switch.WEB_SEARCH.value,
    result_budget=2_000,
    timeout=SEARCH_TIMEOUT,
    provenance=Provenance.WEB,
    step_detail="query",
    previews=(SEARCH_CARD,),
)
WEB_TOOLS: Final = (WEB_SEARCH_SPEC,)


class WebChats(Protocol):
    """The provider port's one-answer chat, as the search uses it."""

    async def chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> ChatResult:
        """The model's whole answer."""
        ...


def source_of(page: Citation) -> SourceRef:
    """A found page as a source of the answer: its address is its id, its site its space."""
    title = page.title.strip() or urlsplit(page.url).hostname or page.url
    return SourceRef(
        SourceKind.WEB, id=page.url, title=title[:TITLE_MAX], quote=page.snippet[:SNIPPET_MAX]
    )


def citable(pages: tuple[Citation, ...]) -> list[Citation]:
    """The pages that can be sources, at most the search's page count."""
    return [page for page in pages if len(page.url) <= SOURCE_ID_MAX][:PAGES]


def web_tools(ai: WebChats, route: Callable[[], ModelRoute | None]) -> tuple[AgentTool, ...]:
    """The web toolset bound to the provider port and the standard model's route."""

    async def search(
        arguments: WebSearchInput, context: ToolContext
    ) -> ToolResult[WebSearchOutput]:
        chosen = route()
        if chosen is None:
            return ToolResult.failed(ToolErrorCode.UNAVAILABLE)
        call = CallContext(
            effect_key=f"{SEARCH_FEATURE}:{context.run_id}:{uuid4().hex}",
            feature=SEARCH_FEATURE,
            call_class=CallClass.STANDARD,
            origin=CallOrigin.INTERACTIVE,
            scope=context.scope,
            # Ход из дома RU допущен только с согласием на передачу: поиск — часть этого хода.
            cross_border_consent=True,
            deadline=SEARCH_TIMEOUT,
        )
        request = ChatRequest(
            messages=(
                text_message(Role.SYSTEM, WEB_SEARCH),
                text_message(Role.USER, arguments.query),
            ),
            max_output_tokens=ANSWER_TOKENS,
            web_search_results=PAGES,
        )
        try:
            answer = await ai.chat(call, chosen, request)
        except AiCallError as error:
            return ToolResult.failed(FAILURE_CODES.get(error.failure, ToolErrorCode.UNAVAILABLE))
        pages = citable(answer.citations)
        output = WebSearchOutput(
            answer=answer.text,
            pages=[
                WebHit(title=p.title, url=p.url, snippet=p.snippet[:SNIPPET_MAX]) for p in pages
            ],
        )
        return ToolResult(output, sources=tuple(source_of(page) for page in pages))

    return (ReadTool(WEB_SEARCH_SPEC, search),)

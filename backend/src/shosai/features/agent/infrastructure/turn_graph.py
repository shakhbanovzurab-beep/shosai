"""The frame of a turn in LangGraph (ADR 0068 AG-D14): nodes, edges and the state between them.

LangGraph only moves a turn from node to node: `context → model`, then `tools → model` for as
long as the model calls tools, and `respond` once it answers — or once a round proposed a
write, whose card the person now decides (step 9a): the turn then ends paused. What each node
does is ours and comes in as the run's steps: the context we build, the model call through the
provider port — which decides what each round may call, so the tenth has no tools and the loop
always ends — the calls we run, the answer we keep. Nothing of LangGraph's ready agents, tool
nodes, model clients, savers or memory is used; a paused turn keeps nothing in the frame — its
action and its rows are in the database — so the graph is compiled without a checkpointer,
once per process.
"""

from dataclasses import dataclass
from typing import Protocol, TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime

from shosai.core.ai.requests import ChatRequest, ToolCall
from shosai.core.ai.results import Usage
from shosai.features.agent.domain.budgets import HARD_ROUNDS

# Причина остановки модели, после которой ответ обрезан пределом токенов.
LENGTH_FINISH = "length"
# Узлов за ход не больше: контекст, по модели и инструментам на раунд, ответ — с запасом.
STEPS_LIMIT = 2 * HARD_ROUNDS + 4


@dataclass(frozen=True, slots=True)
class ModelAnswer:
    """What the model wrote, why it stopped and what the call used."""

    text: str
    finish_reason: str | None
    usage: Usage | None
    first_token_ms: int | None
    # Модель маршрута, которая ответила: основная или запасная.
    model: str | None = None
    # Инструменты, которые модель вызвала в этом раунде; пусто — это ответ.
    tool_calls: tuple[ToolCall, ...] = ()


@dataclass(frozen=True, slots=True)
class TurnAnswer:
    """The answer a turn keeps: the model's, whether a token limit cut it, and the action
    the turn paused for."""

    model: ModelAnswer
    truncated: bool
    paused: UUID | None = None


class TurnSteps(Protocol):
    """What the nodes of one run do: ours, given to the frame for that run."""

    async def context(self) -> ChatRequest:
        """The request for the model: the policy, the conversation and the question."""
        ...

    async def model(self, request: ChatRequest) -> ModelAnswer:
        """The model's answer, streamed into the run's log as it is written."""
        ...

    async def tools(self, request: ChatRequest, answer: ModelAnswer) -> ChatRequest:
        """Run the calls of the answer; the conversation with them and their results."""
        ...

    def paused(self) -> UUID | None:
        """The action the turn proposed and now waits for, if it did."""
        ...


@dataclass(frozen=True, slots=True)
class TurnContext:
    """The run's steps, as LangGraph's runtime context of one invocation."""

    steps: TurnSteps


class TurnState(TypedDict, total=False):
    """What the nodes hand on."""

    request: ChatRequest
    answer: ModelAnswer
    kept: TurnAnswer
    paused: UUID | None


async def context_node(state: TurnState, runtime: Runtime[TurnContext]) -> TurnState:
    """Build the request."""
    del state
    return {"request": await runtime.context.steps.context()}


async def model_node(state: TurnState, runtime: Runtime[TurnContext]) -> TurnState:
    """Call the model."""
    return {"answer": await runtime.context.steps.model(state["request"])}


async def tools_node(state: TurnState, runtime: Runtime[TurnContext]) -> TurnState:
    """Run the tools the model called; note the action a write call proposed."""
    steps = runtime.context.steps
    request = await steps.tools(state["request"], state["answer"])
    return {"request": request, "paused": steps.paused()}


def after_tools(state: TurnState) -> str:
    """Back to the model, or to the answer when a write waits for the person."""
    return "respond" if state.get("paused") else "model"


def after_model(state: TurnState) -> str:
    """To the tools while the model calls them, else to the answer."""
    return "tools" if state["answer"].tool_calls else "respond"


async def respond_node(state: TurnState) -> TurnState:
    """Keep the answer, noting a cut by the token limit and the action it waits for."""
    answer = state["answer"]
    truncated = answer.finish_reason == LENGTH_FINISH
    return {"kept": TurnAnswer(answer, truncated=truncated, paused=state.get("paused"))}


type TurnGraph = CompiledStateGraph[TurnState, TurnContext, TurnState, TurnState]


def turn_graph() -> TurnGraph:
    """The compiled frame; built once per process and shared by its runs."""
    graph = StateGraph(TurnState, context_schema=TurnContext)
    graph.add_node("context", context_node)
    graph.add_node("model", model_node)
    graph.add_node("tools", tools_node)
    graph.add_node("respond", respond_node)
    graph.add_edge(START, "context")
    graph.add_edge("context", "model")
    graph.add_conditional_edges("model", after_model, ["tools", "respond"])
    graph.add_conditional_edges("tools", after_tools, ["model", "respond"])
    graph.add_edge("respond", END)
    return graph.compile()


async def run_turn(graph: TurnGraph, steps: TurnSteps) -> TurnAnswer:
    """Drive one turn through the frame."""
    final = await graph.ainvoke(
        TurnState(), config={"recursion_limit": STEPS_LIMIT}, context=TurnContext(steps)
    )
    kept = final["kept"]
    if not isinstance(kept, TurnAnswer):
        message = "каркас хода закончился без ответа"
        raise TypeError(message)
    return kept

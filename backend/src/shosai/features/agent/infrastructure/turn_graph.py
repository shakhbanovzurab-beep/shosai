"""The frame of a turn in LangGraph (ADR 0068 AG-D14): nodes, edges and the state between them.

LangGraph only moves a turn from node to node: `context → model`, then `tools → model` for as
long as the model calls tools, and `respond` once it answers; the pause for an approval (step
9a) joins the same frame. What each node does is ours and comes in as the run's steps: the
context we build, the model call through the provider port — which decides what each round
may call, so the tenth has no tools and the loop always ends — the calls we run, the answer we
keep. Nothing of LangGraph's ready agents, tool nodes, model clients, savers or memory is used;
without a pause there is nothing to save, so the graph is compiled without a checkpointer, once
per process.
"""

from dataclasses import dataclass
from typing import Protocol, TypedDict

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
    """The answer a turn keeps: the model's, and whether a token limit cut it."""

    model: ModelAnswer
    truncated: bool


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


@dataclass(frozen=True, slots=True)
class TurnContext:
    """The run's steps, as LangGraph's runtime context of one invocation."""

    steps: TurnSteps


class TurnState(TypedDict, total=False):
    """What the nodes hand on."""

    request: ChatRequest
    answer: ModelAnswer
    kept: TurnAnswer


async def context_node(state: TurnState, runtime: Runtime[TurnContext]) -> TurnState:
    """Build the request."""
    del state
    return {"request": await runtime.context.steps.context()}


async def model_node(state: TurnState, runtime: Runtime[TurnContext]) -> TurnState:
    """Call the model."""
    return {"answer": await runtime.context.steps.model(state["request"])}


async def tools_node(state: TurnState, runtime: Runtime[TurnContext]) -> TurnState:
    """Run the tools the model called."""
    return {"request": await runtime.context.steps.tools(state["request"], state["answer"])}


def after_model(state: TurnState) -> str:
    """To the tools while the model calls them, else to the answer."""
    return "tools" if state["answer"].tool_calls else "respond"


async def respond_node(state: TurnState) -> TurnState:
    """Keep the answer, noting a cut by the token limit."""
    answer = state["answer"]
    return {"kept": TurnAnswer(answer, truncated=answer.finish_reason == LENGTH_FINISH)}


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
    graph.add_edge("tools", "model")
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

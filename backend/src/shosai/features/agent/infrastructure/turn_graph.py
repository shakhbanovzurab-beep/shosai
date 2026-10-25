"""The frame of a turn in LangGraph (ADR 0068 AG-D14): nodes, edges, the state between them, and
the pause for a card.

LangGraph only moves a turn from node to node: `context → model`, then `tools → model` for as
long as the model calls tools, and the end once it answers. A round that proposed a write goes
to `approval`, which pauses the turn with LangGraph's interrupt: the frame is saved by our saver
(`turn_saver.py`) and the turn ends paused on its card. The person's decision resumes it in the
same run — `approval` is entered again, the run's steps rebuild the conversation from the
database with what became of the action, and the model writes the epilogue (Leo §5.3). The
state holds references only: the turn's terms, whether the last round called tools or was cut,
and the action it waits for; the conversation stays with the run's steps. What each node does
is ours and comes in as the run's steps: the context we build, the model call through the
provider port — which decides what each round may call, so the tenth has no tools and the loop
always ends — and the calls we run. Nothing of LangGraph's ready agents, tool nodes, model
clients, savers or memory is used. The graph is compiled once per process with our saver, which
keeps each step's checkpoint in the background of the next (`durability="async"`), so the
frame costs the turn no wait.
"""

from dataclasses import dataclass
from typing import Any, Final, Protocol, TypedDict
from uuid import UUID

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt
from pydantic import JsonValue

from shosai.core.ai.requests import ToolCall
from shosai.core.ai.results import Usage
from shosai.features.agent.domain.budgets import HARD_ROUNDS

# Причина остановки модели, после которой ответ обрезан пределом токенов.
LENGTH_FINISH: Final = "length"
# Узлов за ход не больше: контекст, по модели, инструментам и одобрению на раунд — с запасом.
STEPS_LIMIT: Final = 3 * HARD_ROUNDS + 4
# Ключ LangGraph, под которым кадр отдаёт прерывания, на которых он встал.
INTERRUPTS: Final = "__interrupt__"


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
    """How the turn stopped: the model's last answer, whether a token limit cut it, and the
    action it paused for."""

    model: ModelAnswer
    truncated: bool
    paused: UUID | None = None


class TurnSteps(Protocol):
    """What the nodes of one run do: ours, given to the frame for that run."""

    async def context(self) -> None:
        """Build the request for the model: the policy, the conversation and the question."""
        ...

    async def model(self) -> ModelAnswer:
        """The next round's answer, streamed into the run's log as it is written."""
        ...

    async def tools(self) -> UUID | None:
        """Run the calls of the last answer; the action a write call proposed, if one did."""
        ...

    async def resume(self, action_id: UUID) -> None:
        """After the person's decision: the conversation again, with what became of it."""
        ...

    def answer(self) -> ModelAnswer | None:
        """The model's last answer in this run, if it gave one."""
        ...


@dataclass(frozen=True, slots=True)
class TurnContext:
    """The run's steps, as LangGraph's runtime context of one invocation."""

    steps: TurnSteps


class TurnState(TypedDict, total=False):
    """What the nodes hand on and the saver keeps: references, never the conversation."""

    # Условия хода (полезная нагрузка задачи): по ним воркер поднимает ход после решения.
    turn: dict[str, JsonValue]
    calls: bool
    truncated: bool
    paused: str | None


async def context_node(state: TurnState, runtime: Runtime[TurnContext]) -> TurnState:
    """Build the request."""
    del state
    await runtime.context.steps.context()
    return {"paused": None}


async def model_node(state: TurnState, runtime: Runtime[TurnContext]) -> TurnState:
    """Call the model."""
    del state
    answer = await runtime.context.steps.model()
    return {"calls": bool(answer.tool_calls), "truncated": answer.finish_reason == LENGTH_FINISH}


async def tools_node(state: TurnState, runtime: Runtime[TurnContext]) -> TurnState:
    """Run the tools the model called; note the action a write call proposed."""
    del state
    proposed = await runtime.context.steps.tools()
    return {"paused": None if proposed is None else str(proposed)}


async def approval_node(state: TurnState, runtime: Runtime[TurnContext]) -> TurnState:
    """Pause on the card; entered again after the decision, go on with what became of it."""
    decided = interrupt(state.get("paused"))
    await runtime.context.steps.resume(UUID(str(decided)))
    return {"paused": None}


def after_model(state: TurnState) -> str:
    """To the tools while the model calls them, else the turn is answered."""
    return "tools" if state.get("calls") else END


def after_tools(state: TurnState) -> str:
    """Back to the model, or to the pause when a write waits for the person."""
    return "approval" if state.get("paused") else "model"


type TurnGraph = CompiledStateGraph[TurnState, TurnContext, TurnState, TurnState]


def turn_graph(saver: BaseCheckpointSaver[int]) -> TurnGraph:
    """The compiled frame with our saver; built once per process and shared by its runs."""
    graph = StateGraph(TurnState, context_schema=TurnContext)
    graph.add_node("context", context_node)
    graph.add_node("model", model_node)
    graph.add_node("tools", tools_node)
    graph.add_node("approval", approval_node)
    graph.add_edge(START, "context")
    graph.add_edge("context", "model")
    graph.add_conditional_edges("model", after_model, ["tools", END])
    graph.add_conditional_edges("tools", after_tools, ["model", "approval"])
    graph.add_edge("approval", "model")
    return graph.compile(checkpointer=saver)


async def run_turn(
    graph: TurnGraph, steps: TurnSteps, run_id: UUID, terms: dict[str, JsonValue]
) -> TurnAnswer:
    """Drive a new turn through the frame."""
    final = await graph.ainvoke(
        TurnState(turn=terms),
        config={"configurable": {"thread_id": str(run_id)}, "recursion_limit": STEPS_LIMIT},
        context=TurnContext(steps),
        durability="async",
    )
    return stopped_at(final, steps)


async def resume_turn(
    graph: TurnGraph, steps: TurnSteps, run_id: UUID, action_id: UUID
) -> TurnAnswer:
    """Drive a paused turn on from its card, once its action is decided."""
    final = await graph.ainvoke(
        Command(resume=str(action_id)),
        config={"configurable": {"thread_id": str(run_id)}, "recursion_limit": STEPS_LIMIT},
        context=TurnContext(steps),
        durability="async",
    )
    return stopped_at(final, steps)


def stopped_at(final: dict[str, Any], steps: TurnSteps) -> TurnAnswer:
    """How the frame stopped: answered, cut, or paused on a card."""
    answer = steps.answer()
    if answer is None:
        message = "каркас хода закончился без ответа модели"
        raise TypeError(message)
    interrupts = final.get(INTERRUPTS) or ()
    paused = UUID(str(interrupts[0].value)) if interrupts else None
    truncated = paused is None and final.get("truncated") is True
    return TurnAnswer(answer, truncated=truncated, paused=paused)


async def paused_terms(graph: TurnGraph, run_id: UUID) -> dict[str, JsonValue] | None:
    """The terms of a turn the frame keeps paused on a card; None when it keeps none."""
    snapshot = await graph.aget_state({"configurable": {"thread_id": str(run_id)}})
    terms = snapshot.values.get("turn") if snapshot.interrupts else None
    return dict(terms) if isinstance(terms, dict) else None

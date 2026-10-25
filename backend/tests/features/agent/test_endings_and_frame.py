"""A run's ending in its row, its answer and its stream; the LangGraph parts the slice uses."""

import ast
import uuid
from pathlib import Path
from typing import Final

from hypothesis import given
from hypothesis import strategies as st

from shosai.features.agent.domain.endings import (
    answered,
    cancelled,
    failed,
    recorded,
    stopped,
)
from shosai.features.agent.domain.runs import RunFailure, RunStatus
from shosai.features.agent.domain.stream import EventKind
from shosai.features.agent.domain.threads import AnswerStatus

SOURCE: Final = Path(__file__).parents[3] / "src" / "shosai"
FRAME: Final = SOURCE / "features" / "agent" / "infrastructure"
# Публичные части LangGraph, из которых собраны каркас хода и наш сохранитель (AG-D14): граф,
# рантайм, прерывание, интерфейс сохранителя и тип его настроек; готовые агенты, ToolNode,
# сохранители, хранилище и клиенты моделей сюда не входят.
ALLOWED: Final = frozenset(
    {
        "langgraph.graph", "langgraph.graph.state", "langgraph.runtime", "langgraph.types",
        "langgraph.checkpoint.base", "langchain_core.runnables",
    }
)  # fmt: skip
PLACES: Final = frozenset({"turn_graph.py", "turn_saver.py"})


@given(st.sampled_from(RunFailure), st.text(max_size=5))
def test_a_failure_closes_the_stream_with_its_code_and_keeps_only_written_text(
    failure: RunFailure, text: str
) -> None:
    ending = failed(failure)

    assert ending.terminal(uuid.uuid4()) == (EventKind.RUN_FAILED, {"code": failure.value})
    assert ending.keeps(text) == bool(text)
    assert recorded(RunStatus.FAILED, failure.value) == ending


def test_an_answer_a_stop_and_a_deleted_thread_close_the_stream_as_completed() -> None:
    reply = uuid.uuid4()

    assert answered(truncated=True).terminal(reply) == (
        EventKind.RUN_COMPLETED,
        {"message_id": str(reply), "outcome": "answered", "truncated": True},
    )
    assert stopped().terminal(None)[1]["outcome"] == "stopped"
    assert cancelled().terminal(reply)[1]["outcome"] == "stopped"
    assert answered(truncated=False).keeps("")
    assert not stopped().keeps("")
    assert not cancelled().keeps("text")
    assert (stopped().answer, cancelled().status) == (AnswerStatus.STOPPED, RunStatus.CANCELLED)
    assert recorded(RunStatus.RUNNING, None) is None
    assert recorded(RunStatus.FAILED, "unknown") == failed(RunFailure.FAILED)


def test_langgraph_is_imported_only_by_the_frame_and_only_its_public_parts() -> None:
    found: dict[str, set[str]] = {}
    for path in SOURCE.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            for name in names:
                if name.split(".")[0] in {"langgraph", "langchain", "langchain_core"}:
                    found.setdefault(name, set()).add(str(path.relative_to(SOURCE)))

    assert set(found) <= ALLOWED
    assert {place for places in found.values() for place in places} <= {
        str((FRAME / name).relative_to(SOURCE)) for name in PLACES
    }

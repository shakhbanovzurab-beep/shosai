"""Calls the boards' tests share: a new board, its read, its columns and their cards."""

import uuid
from typing import Any

import httpx

from tests.features.tasks.task_bench import TaskBench


def code_of(answer: httpx.Response) -> str:
    """The refusal's code in the platform's envelope."""
    return str(answer.json()["error"]["code"])


async def made(bench: TaskBench, who: uuid.UUID, template: str = "simple", **headers: str) -> str:
    """A new board's id."""
    body = {"name": "Работа", "icon": "briefcase", "template": template}
    answer = await bench.call(who, "POST", "/v1/boards", body, **headers)
    assert answer.status_code == 201, answer.text
    return str(answer.json()["id"])


async def board(bench: TaskBench, who: uuid.UUID, board_id: str) -> dict[str, Any]:
    """The board as its screen reads it."""
    answer = await bench.call(who, "GET", f"/v1/boards/{board_id}")
    assert answer.status_code == 200, answer.text
    return dict(answer.json())


def column_ids(detail: dict[str, Any]) -> list[str]:
    """The board's columns, left to right."""
    return [str(column["id"]) for column in detail["columns"]]


def cards_of(detail: dict[str, Any], index: int) -> list[str]:
    """The cards of a column, top to bottom."""
    return [str(card["id"]) for card in detail["columns"][index]["cards"]]

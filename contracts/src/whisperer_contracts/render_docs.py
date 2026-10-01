"""Сборка Markdown-документов базы из её JSON: единственный источник правды — JSON."""

from pathlib import Path

from whisperer_contracts.jsonvalue import Json, as_object, load_json, optional_object, optional_str
from whisperer_contracts.render_consumers import render_consumers
from whisperer_contracts.render_websocket import render_websocket


def _preamble(draft: Json) -> str:
    """Откуда снята база: репозиторий, коммит, дата и способ."""
    info = optional_object(draft)
    return (
        f"Captured from the draft repository `{optional_str(info.get('repository'))}` at commit "
        f"`{optional_str(info.get('commit'))}` on {optional_str(info.get('captured_on'))}. "
        f"{optional_str(info.get('method'))} File references point into the draft repository."
    )


def render_baseline_documents(directory: Path) -> dict[str, str]:
    """Тексты `consumers.md` и `websocket.md` для каталога базы."""
    consumers = as_object(load_json(directory / "consumers.json"), "consumers.json")
    websocket = as_object(load_json(directory / "websocket.json"), "websocket.json")
    openapi = as_object(load_json(directory / "openapi.json"), "openapi.json")
    return {
        "consumers.md": render_consumers(consumers, openapi, _preamble(consumers.get("draft"))),
        "websocket.md": render_websocket(websocket, _preamble(websocket.get("draft"))),
    }

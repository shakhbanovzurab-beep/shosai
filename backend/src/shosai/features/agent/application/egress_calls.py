"""A call that sends data outside Shosai, carried as a card on a tainted run (Leo §7.4; step 13b).

Once a run has read text from outside Shosai, a call that sends data out — a web search — could
carry that text's orders with it, so it waits for the person's card instead of running. The
card's item keeps the call's arguments and the id of the model's call, and its words are the
tool's one wording, filled from the arguments. Approved, the call runs once, as the person,
within its timeout; its result — the output and the sources it names — is kept as one of the
run's results, and the item names it, for the epilogue to read back as the call's own answer.
A failure fails the item with the tool's code: nothing of a search can have taken effect.
"""

import asyncio
from collections.abc import Mapping
from typing import Any, Final

import structlog
from pydantic import BaseModel, JsonValue, ValidationError

from shosai.core.agent_tools.bindings import ReadTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import ToolErrorCode, ToolResult
from shosai.core.agent_tools.sources import SourceRef
from shosai.core.agent_tools.spec import Reversibility, ToolEffect, ToolSpec
from shosai.features.agent.application.result_pages import ResultPages
from shosai.features.agent.domain.action_items import ActionItem, ItemState, params_of, redacted
from shosai.features.agent.domain.digests import compact

ARGUMENTS: Final = "arguments"
CALL_ID: Final = "call_id"
OUTPUT: Final = "output"
SOURCES: Final = "sources"
log = structlog.stdlib.get_logger(__name__)


def is_egress(spec: ToolSpec[Any, Any]) -> bool:
    """Whether the tool sends data outside Shosai."""
    return spec.effect is ToolEffect.EGRESS


def egress_item(spec: ToolSpec[Any, Any], arguments: BaseModel, call_id: str) -> ActionItem | None:
    """The card's item of the call; None for a tool with no words for its card."""
    if len(spec.previews) != 1:
        return None
    (wording,) = spec.previews
    values: dict[str, JsonValue] = arguments.model_dump(mode="json")
    return ActionItem(
        tool=spec.name, targets=(), plan={ARGUMENTS: values, CALL_ID: call_id},
        fields=redacted(values), preview_key=wording.key,
        preview_params=params_of({name: values.get(name) for name in wording.params}),
        # Отправленное наружу не вернуть: карточка так и говорит.
        reversibility=Reversibility.IRREVERSIBLE.value, effect=ToolEffect.EGRESS.value,
    )  # fmt: skip


def stored_source(ref: SourceRef) -> dict[str, JsonValue]:
    """A source as the kept result holds it."""
    return {
        "kind": ref.kind.value, "id": ref.id, "title": ref.title,
        "org_id": None if ref.org_id is None else str(ref.org_id),
        "locator": ref.locator, "quote": ref.quote,
    }  # fmt: skip


def kept_payload(result: ToolResult[Any]) -> str:
    """What is kept of an approved call's result: its output and its sources."""
    output = result.output.model_dump(mode="json") if result.output is not None else {}
    return compact({OUTPUT: output, SOURCES: [stored_source(ref) for ref in result.sources]})


class EgressCalls:
    """Runs the approved egress items of actions."""

    def __init__(self, pages: ResultPages) -> None:
        self._pages = pages

    async def run(
        self, tool: ReadTool[Any, Any], item: ActionItem, context: ToolContext
    ) -> ActionItem:
        """The item after its call: succeeded with its kept result, or failed with a code."""
        spec = tool.spec
        raw = item.plan.get(ARGUMENTS)
        try:
            arguments = spec.input.model_validate(raw if isinstance(raw, Mapping) else {})
        except ValidationError:
            return item.with_state(ItemState.FAILED, ToolErrorCode.INVALID_ARGUMENTS.value)
        try:
            async with asyncio.timeout(spec.timeout.total_seconds()):
                result = await tool.run(arguments, context)
        except TimeoutError:
            return item.with_state(ItemState.FAILED, ToolErrorCode.TIMEOUT.value)
        # Сбой инструмента после одобрения: у поиска нет эффекта, который мог бы остаться.
        except Exception:
            log.exception("Одобренный вызов Leo наружу упал", tool=spec.name)
            return item.with_state(ItemState.FAILED, ToolErrorCode.FAILED.value)
        if result.error is not None:
            return item.with_state(ItemState.FAILED, result.error.code.value)
        kept = await self._pages.keep(context, spec.name, kept_payload(result))
        return item.with_result(str(kept))

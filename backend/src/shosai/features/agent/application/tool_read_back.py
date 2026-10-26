"""What the model reads of a call's result: the result or its digest, its sources, its label.

A result names its sources: the run numbers them and the model reads them beside the result
as `sources`, which an answer cites by `[n]`. A result over its tool's budget is kept whole and
read as a digest with its reference, its sources always whole. Text with a label — the result's
own when it narrows the spec's, a page of a kept result with its tool's — is wrapped with the
run's boundary and raises the run's taint (Leo §7.4).
"""

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import JsonValue

from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.provenance import Provenance
from shosai.core.agent_tools.results import ToolError, ToolErrorCode, ToolResult
from shosai.features.agent.application.result_pages import ResultPages
from shosai.features.agent.application.run_attachments import ATTACHMENT_RESULT
from shosai.features.agent.application.run_sources import RunSources
from shosai.features.agent.application.run_work import RunWork
from shosai.features.agent.application.tool_answers import digest_content, error_content
from shosai.features.agent.application.tool_offer import TurnOffer
from shosai.features.agent.application.tool_registry import SOURCES_FIELD, OfferedTool
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.domain.budgets import estimate_tokens, over_budget
from shosai.features.agent.domain.core_tools import READ_RESULT
from shosai.features.agent.domain.digests import compact
from shosai.features.agent.domain.wrapper import Label, wrap


@dataclass(frozen=True, slots=True)
class ReadBack:
    """What the model reads, the kept whole result if any, and whether the sources grew."""

    text: str
    result_id: UUID | None = None
    new_sources: bool = False


class ResultReader:
    """Turns a call's result into what the model reads, for one run."""

    def __init__(
        self,
        parts: tuple[ResultPages, RunSources, asyncio.Semaphore],
        run: tuple[TurnPayload, RunWork],
    ) -> None:
        self._pages, self._sources, self._bulkhead = parts
        self._payload, self._work = run

    async def read(
        self, offer: TurnOffer, offered: OfferedTool, result: ToolResult[Any], context: ToolContext
    ) -> ReadBack:
        """The result as the model reads it."""
        if result.output is None:
            return ReadBack(error_content(result.error or ToolError(ToolErrorCode.FAILED)))
        spec = offered.spec
        cites: list[JsonValue] = []
        grew = False
        if result.sources:
            numbered, grew = await self._sources.admit(self._work, self._payload, result.sources)
            cites = list(numbered)
        value: dict[str, JsonValue] = result.output.model_dump(mode="json")
        whole = value | {SOURCES_FIELD: cites} if cites else value
        text, result_id = compact(whole), None
        if spec.name != READ_RESULT and over_budget(estimate_tokens(text), spec.result_budget):
            async with self._bulkhead:
                result_id = await self._pages.keep(context, spec.name, text)
            text = digest_content(value, spec.result_budget, result_id, cites)
        provenance = self._provenance(offer, offered, result)
        if provenance is not None:
            label = Label.of(provenance)
            text = wrap(text, label, self._work.token)
            self._work.read_wrapped(label)
        return ReadBack(text, result_id, grew)

    @staticmethod
    def _provenance(
        offer: TurnOffer, offered: OfferedTool, result: ToolResult[Any]
    ) -> Provenance | None:
        """The result's own label, else its spec's; a kept page takes its tool's."""
        if offered.spec.name != READ_RESULT:
            return result.provenance or offered.spec.provenance
        kept = str(getattr(result.output, "tool", ""))
        if kept == ATTACHMENT_RESULT:
            return Provenance.FILE_OWN
        origin = offer.kept_from(kept)
        # Инструмента хранимого результата больше нет: это прочитанное раньше, метка памяти.
        return origin.spec.provenance if origin is not None else Provenance.MEMORY

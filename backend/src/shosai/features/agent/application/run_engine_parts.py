"""What the engine of the `agent` queue's workers works with (AG-D12; agent steps 5a, 6).

The provider port's streaming chat as the engine uses it, the run's stores and its log, the
leases and the fleet, the compiled frame and our saver of it, the context builder and the
routing of tools, the tools' bulkhead and pages, the telemetry, and the stream's pace.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from shosai.core.ai.calls import CallContext, ModelRoute
from shosai.core.ai.requests import ChatRequest
from shosai.core.ai.results import ChatDelta
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.model_stream import DEFAULT_PACE, Pace
from shosai.features.agent.application.run_attachments import AttachmentReader
from shosai.features.agent.application.run_context import ContextBuilder
from shosai.features.agent.application.run_registry import RunRegistry
from shosai.features.agent.application.run_telemetry import RunTelemetry
from shosai.features.agent.application.tool_offer import TurnRouting
from shosai.features.agent.application.tool_round import ToolParts
from shosai.features.agent.infrastructure.fleet import Fleet
from shosai.features.agent.infrastructure.run_log import RunLog
from shosai.features.agent.infrastructure.thread_lease import ThreadLeases
from shosai.features.agent.infrastructure.turn_graph import TurnGraph
from shosai.features.agent.infrastructure.turn_saver import TurnSaver


class ModelStreams(Protocol):
    """The provider port's streaming chat, as the engine uses it."""

    def stream_chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> AsyncIterator[ChatDelta]:
        """The model's answer as it is written."""
        ...


@dataclass(frozen=True, slots=True)
class EngineParts:
    """What the engine works with in an agent worker."""

    transactions: HomeTransactions
    ai: ModelStreams
    route: ModelRoute | None
    run_log: RunLog
    leases: ThreadLeases
    fleet: Fleet
    registry: RunRegistry
    outbox: EventOutbox
    graph: TurnGraph
    frames: TurnSaver
    context: ContextBuilder
    routing: TurnRouting
    tools: ToolParts
    telemetry: RunTelemetry
    attachments: AttachmentReader
    pace: Pace = DEFAULT_PACE
    # Порты срезов: судья подсказок в тексте (decisions' `content.injection`), когда привязан.
    ports: PortDirectory | None = None

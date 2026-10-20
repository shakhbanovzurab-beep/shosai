"""The pipeline's stage handlers this process runs, from its settings (plan steps 6 and 9a).

The findings and write-up stages need the notes' model; the intake and transcribe stages
need the transcription model and the tools — `ffprobe`, `ffmpeg` and `prlimit` — on the
path (the runtime image has them). A stage without its handler waits for a process that
has it, so a development machine without a model or the tools leaves runs pending.
"""

import shutil
from typing import Final

import structlog

from shosai.core.ai.calls import ModelRef, ModelRoute, Provider
from shosai.core.features import CoreServices
from shosai.features.meetings.application.findings_stage import FindingsStage
from shosai.features.meetings.application.intake_stage import IntakeStage
from shosai.features.meetings.application.notes_model import NotesModel
from shosai.features.meetings.application.pipeline import StageHandler
from shosai.features.meetings.application.stage_reads import transcript_budget
from shosai.features.meetings.application.transcribe_stage import TranscribeStage
from shosai.features.meetings.application.write_up_stage import WriteUpStage
from shosai.features.meetings.domain.runs import Stage
from shosai.features.meetings.infrastructure.media_tools import MediaLimits, MediaTools
from shosai.features.meetings.infrastructure.notes_metrics import NotesMetrics
from shosai.features.meetings.settings import MeetingsSettings

TOOLS: Final = ("ffprobe", "ffmpeg", "prlimit")
log = structlog.stdlib.get_logger(__name__)


def route_of(model: str, fallback: str | None) -> ModelRoute:
    """An OpenRouter model and its optional fallback."""
    return ModelRoute(
        ModelRef(Provider.OPENROUTER, model),
        fallbacks=(ModelRef(Provider.OPENROUTER, fallback),) if fallback else (),
    )


def notes_stages(services: CoreServices) -> dict[Stage, StageHandler]:
    """The findings and write-up stages over the configured model; none without one."""
    settings = services.settings.features.get(MeetingsSettings)
    metrics = NotesMetrics(services.registry)
    if not settings.meetings_notes_model:
        return {}
    route = route_of(settings.meetings_notes_model, settings.meetings_notes_fallback_model)
    model = NotesModel(services.ai, route, metrics)
    budget = transcript_budget(services.settings.ai_guards.ai_max_context_tokens)
    transactions, ports = services.transactions, services.ports
    return {
        Stage.FINDINGS: FindingsStage(transactions, (ports, model), budget),
        Stage.WRITE_UP: WriteUpStage(transactions, (ports, services.outbox, model), budget),
    }


def recording_stages(services: CoreServices) -> dict[Stage, StageHandler]:
    """The intake and transcribe stages over the transcription model and the tools."""
    settings = services.settings.features.get(MeetingsSettings)
    if not settings.meetings_transcribe_model:
        return {}
    missing = [tool for tool in TOOLS if shutil.which(tool) is None]
    if missing:
        log.warning("Нет инструментов медиа: записи не расшифровываются", missing=missing)
        return {}
    tools = MediaTools(
        MediaLimits(settings.meetings_media_seconds, settings.meetings_media_memory_mb)
    )
    route = route_of(
        settings.meetings_transcribe_model, settings.meetings_transcribe_fallback_model
    )
    transactions, ports, objects = services.transactions, services.ports, services.objects
    return {
        Stage.INTAKE: IntakeStage(transactions, (ports, objects, tools)),
        Stage.TRANSCRIBE: TranscribeStage(
            transactions, (ports, objects, tools), (services.ai, route)
        ),
    }


def pipeline_stages(services: CoreServices) -> dict[Stage, StageHandler]:
    """Every stage handler this process runs."""
    return {**notes_stages(services), **recording_stages(services)}

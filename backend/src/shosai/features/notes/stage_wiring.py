"""The pipeline's stage handlers this process runs, from its settings (plan steps 6, 9a, 10).

The findings and write-up stages need the notes' model; the recording's stages — intake,
transcribe, diarize and align — need the transcription and diarization models and the
tools — `ffprobe`, `ffmpeg` and `prlimit` — on the path (the runtime image has them). A
stage without its handler waits for a process that has it, so a development machine
without a model or the tools leaves runs pending.
"""

import shutil
from typing import Final

import structlog

from shosai.core.ai.calls import ModelRef, ModelRoute, Provider
from shosai.core.features import CoreServices
from shosai.features.notes.application.align_stage import AlignStage
from shosai.features.notes.application.diarize_stage import DiarizeStage
from shosai.features.notes.application.findings_stage import FindingsStage
from shosai.features.notes.application.intake_stage import IntakeStage
from shosai.features.notes.application.notes_model import NotesModel
from shosai.features.notes.application.pipeline import StageHandler
from shosai.features.notes.application.stage_reads import transcript_budget
from shosai.features.notes.application.transcribe_stage import TranscribeStage
from shosai.features.notes.application.write_up_stage import WriteUpStage
from shosai.features.notes.domain.runs import Stage
from shosai.features.notes.infrastructure.media_tools import MediaLimits, MediaTools
from shosai.features.notes.infrastructure.notes_metrics import NotesMetrics
from shosai.features.notes.infrastructure.transcript_archive import TranscriptArchive
from shosai.features.notes.settings import NotesSettings

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
    settings = services.settings.features.get(NotesSettings)
    metrics = NotesMetrics(services.registry)
    if not settings.notes_model:
        return {}
    route = route_of(settings.notes_model, settings.notes_fallback_model)
    model = NotesModel(services.ai, route, metrics)
    budget = transcript_budget(services.settings.ai_guards.ai_max_context_tokens)
    transactions, ports = services.transactions, services.ports
    archive = TranscriptArchive(services.objects)
    return {
        Stage.FINDINGS: FindingsStage(transactions, (ports, model, archive), budget),
        Stage.WRITE_UP: WriteUpStage(
            transactions, (ports, services.outbox, model, archive), budget
        ),
    }


def recording_stages(services: CoreServices) -> dict[Stage, StageHandler]:
    """The recording's stages over the transcription and diarization models and the tools."""
    settings = services.settings.features.get(NotesSettings)
    if not settings.notes_transcribe_model or not settings.notes_diarize_model:
        return {}
    missing = [tool for tool in TOOLS if shutil.which(tool) is None]
    if missing:
        log.warning("Нет инструментов медиа: записи не расшифровываются", missing=missing)
        return {}
    tools = MediaTools(MediaLimits(settings.notes_media_seconds, settings.notes_media_memory_mb))
    route = route_of(settings.notes_transcribe_model, settings.notes_transcribe_fallback_model)
    diarizer = ModelRoute(ModelRef(Provider.PYANNOTE, settings.notes_diarize_model))
    transactions, ports, objects = services.transactions, services.ports, services.objects
    return {
        Stage.INTAKE: IntakeStage(transactions, (ports, objects, tools)),
        Stage.TRANSCRIBE: TranscribeStage(
            transactions, (ports, objects, tools), (services.ai, route)
        ),
        Stage.DIARIZE: DiarizeStage(transactions, (ports, objects, tools), (services.ai, diarizer)),
        Stage.ALIGN: AlignStage(transactions, objects),
    }


def pipeline_stages(services: CoreServices) -> dict[Stage, StageHandler]:
    """Every stage handler this process runs."""
    return {**notes_stages(services), **recording_stages(services)}

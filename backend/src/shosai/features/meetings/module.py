"""The meetings slice as composition sees it (meetings plan §3.1), step by step:

- 1: the contract, the events and the domain;
- 2: the tables, the shareable `meeting` resource and the account data handler;
- 3: the native start and end, §10's end and runs, and billing's count of live meetings;
- 4: the live transcript's store and socket binding for capture, the live and settle sweeps;
- 5: the pipeline's engine and the recovery of runs;
- 6: the findings and write-up stages with the notes' model, and the rewrite of a write-up;
- 7a: the cabinet's library and a meeting's page, transcript, write-up, findings and map;
- 7b: each person's own notes, participants, the template choice, folders and templates;
- 8: the deletion, the purge after 7 days, support's list and restore, the native rename and
  deletion, and identity's deletion window.

The folders' and templates' routes come before `/v1/meetings/{meeting_id}`: the first match
wins, and `folders` is no meeting's id.

Without `MEETINGS_NOTES_MODEL` (development only: production refuses to start) the two
stages have no handler, and runs wait for one.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.ai.calls import ModelRef, ModelRoute, Provider
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.features.billing.contracts import MEETING_MINUTES
from shosai.features.meetings.application.account_data import ACCOUNT_DATA, MeetingsAccountData
from shosai.features.meetings.application.deletion import MeetingDeletion
from shosai.features.meetings.application.findings_stage import FindingsStage
from shosai.features.meetings.application.folders import Folders
from shosai.features.meetings.application.hidden_meetings import HiddenMeetings
from shosai.features.meetings.application.library import MeetingLibrary
from shosai.features.meetings.application.lifecycle import MeetingLifecycle
from shosai.features.meetings.application.live_meetings import LiveMeetingBinder
from shosai.features.meetings.application.live_transcript import LiveTranscript
from shosai.features.meetings.application.meeting_content import MeetingContent
from shosai.features.meetings.application.minutes import MeetingMinutesCount
from shosai.features.meetings.application.my_notes import MyNotes
from shosai.features.meetings.application.notes_model import NotesModel
from shosai.features.meetings.application.participants import Participants
from shosai.features.meetings.application.pipeline import PipelineEngine, StageHandler
from shosai.features.meetings.application.run_recovery import RunRecovery
from shosai.features.meetings.application.runs_view import RunViews
from shosai.features.meetings.application.stage_reads import transcript_budget
from shosai.features.meetings.application.support_meetings import SupportMeetings
from shosai.features.meetings.application.sweeps import MeetingSweeps
from shosai.features.meetings.application.templates import Templates
from shosai.features.meetings.application.write_up_rewrites import WriteUpRewrites
from shosai.features.meetings.application.write_up_stage import WriteUpStage
from shosai.features.meetings.channels.http.admin_meetings import build_admin_meetings_router
from shosai.features.meetings.channels.http.folders import build_folders_router
from shosai.features.meetings.channels.http.meeting_content import build_meeting_content_router
from shosai.features.meetings.channels.http.meetings import build_meetings_router
from shosai.features.meetings.channels.http.my_notes import build_my_notes_router
from shosai.features.meetings.channels.http.native_me_sessions import (
    build_native_me_sessions_router,
)
from shosai.features.meetings.channels.http.native_sessions import build_native_sessions_router
from shosai.features.meetings.channels.http.runs import build_runs_router
from shosai.features.meetings.channels.http.templates import build_templates_router
from shosai.features.meetings.channels.http.write_up import build_write_up_router
from shosai.features.meetings.channels.subscriptions import subscriptions
from shosai.features.meetings.channels.tasks import PERIODIC_JOBS, task_handlers
from shosai.features.meetings.contracts import LIVE_MEETINGS, TRANSCRIPT_STORE
from shosai.features.meetings.contracts.events import (
    MeetingDeleted,
    MeetingEnded,
    MeetingRestored,
    NotesReady,
)
from shosai.features.meetings.domain.runs import Stage
from shosai.features.meetings.infrastructure.meeting_records import (
    MEETING_RESOURCE,
    MeetingRecord,
    ParticipantRecord,
    SpeakerRecord,
    TranscriptLineRecord,
)
from shosai.features.meetings.infrastructure.metrics import MeetingMetrics
from shosai.features.meetings.infrastructure.notes_metrics import NotesMetrics
from shosai.features.meetings.infrastructure.notes_records import (
    FindingRecord,
    FolderRecord,
    NotesRecord,
    SettingsRecord,
    TemplateRecord,
)
from shosai.features.meetings.infrastructure.own_notes_records import OwnNotesRecord
from shosai.features.meetings.infrastructure.pipeline_metrics import PipelineMetrics
from shosai.features.meetings.infrastructure.run_objects import RunObjects
from shosai.features.meetings.infrastructure.run_records import ObjectDeletionRecord, RunRecord
from shosai.features.meetings.infrastructure.share_records import (
    ShareCommentRecord,
    ShareLinkRecord,
)
from shosai.features.meetings.infrastructure.transcript_metrics import TranscriptMetrics
from shosai.features.meetings.objectives import MEETINGS_MONITORS, MEETINGS_OBJECTIVES
from shosai.features.meetings.settings import MeetingsSettings, notes_model_set


def notes_stages(services: CoreServices) -> dict[Stage, StageHandler]:
    """The findings and write-up stages over the configured model; none without one."""
    settings = services.settings.features.get(MeetingsSettings)
    metrics = NotesMetrics(services.registry)
    if not settings.meetings_notes_model:
        return {}
    fallback = settings.meetings_notes_fallback_model
    route = ModelRoute(
        ModelRef(Provider.OPENROUTER, settings.meetings_notes_model),
        fallbacks=(ModelRef(Provider.OPENROUTER, fallback),) if fallback else (),
    )
    model = NotesModel(services.ai, route, metrics)
    budget = transcript_budget(services.settings.ai_guards.ai_max_context_tokens)
    transactions, ports = services.transactions, services.ports
    return {
        Stage.FINDINGS: FindingsStage(transactions, (ports, model), budget),
        Stage.WRITE_UP: WriteUpStage(transactions, (ports, services.outbox, model), budget),
    }


def http_routers(
    services: CoreServices, pipeline: tuple[MeetingLifecycle, PipelineEngine]
) -> tuple[APIRouter, ...]:
    """Meetings' routes; the folders' and templates' come before `/v1/meetings/{meeting_id}`."""
    transactions, ports = services.transactions, services.ports
    lifecycle, engine = pipeline
    library = MeetingLibrary(transactions, ports)
    deletion = MeetingDeletion(transactions, (ports, services.outbox))
    rewrites = WriteUpRewrites(transactions, (ports, services.effects, engine))
    support = SupportMeetings(transactions, (ports, services.outbox))
    return (
        build_folders_router(Folders(transactions, services.effects), ports),
        build_templates_router(Templates(transactions, services.effects), ports),
        build_native_sessions_router(lifecycle, ports),
        build_native_me_sessions_router((library, deletion), ports),
        build_runs_router((lifecycle, RunViews(transactions, ports)), ports),
        build_write_up_router(rewrites, ports, services.rate_limiter),
        build_meetings_router((library, deletion), ports),
        build_meeting_content_router(MeetingContent(transactions, ports), ports),
        build_my_notes_router(
            (MyNotes(transactions, ports), Participants(transactions, ports)), ports
        ),
        build_admin_meetings_router(support, ports),
    )


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """The lifecycle, the pipeline and their routes, billing's count and the account data."""
    transactions, ports = services.transactions, services.ports
    handler = MeetingsAccountData(transactions, (services.objects, services.uploads))
    pipeline_metrics = PipelineMetrics(services.registry)
    # Стадии записи и разметки появляются в следующих шагах плана: до них их прогоны ждут.
    engine = PipelineEngine(
        transactions, (services.tasks, pipeline_metrics, notes_stages(services))
    )
    lifecycle = MeetingLifecycle(
        transactions,
        (ports, services.outbox, MeetingMetrics(services.registry)),
        starter=engine,
    )
    transcript_metrics = TranscriptMetrics(services.registry)
    sweeps = MeetingSweeps(transactions, (ports, lifecycle, transcript_metrics))
    hidden = HiddenMeetings(transactions, (ports, RunObjects(transactions, services.objects)))
    recovery = RunRecovery(transactions, (engine, pipeline_metrics))
    yield FeatureParts(
        http_routers=http_routers(services, (lifecycle, engine)),
        task_handlers=task_handlers((sweeps, hidden), (engine, recovery)),
        subscriptions=subscriptions(),
        periodic_jobs=PERIODIC_JOBS,
        provides=(
            ACCOUNT_DATA_HANDLERS.bind(handler),
            MEETING_MINUTES.bind(MeetingMinutesCount()),
            TRANSCRIPT_STORE.bind(LiveTranscript(transactions, transcript_metrics)),
            LIVE_MEETINGS.bind(LiveMeetingBinder(ports)),
        ),
    )


MEETINGS = FeatureModule(
    name="meetings",
    build=build,
    account_data=(ACCOUNT_DATA,),
    settings=(MeetingsSettings,),
    production_checks=(notes_model_set,),
    objectives=MEETINGS_OBJECTIVES,
    monitors=MEETINGS_MONITORS,
    shareable=(MEETING_RESOURCE,),
    models=(
        FolderRecord,
        TemplateRecord,
        SettingsRecord,
        MeetingRecord,
        TranscriptLineRecord,
        SpeakerRecord,
        ParticipantRecord,
        NotesRecord,
        OwnNotesRecord,
        FindingRecord,
        RunRecord,
        ObjectDeletionRecord,
        ShareLinkRecord,
        ShareCommentRecord,
    ),
    events=(MeetingEnded, NotesReady, MeetingDeleted, MeetingRestored),
)

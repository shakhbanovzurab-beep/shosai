"""The meetings slice as composition sees it (meetings plan §3.1), step by step:

- 1: the contract, the events and the domain;
- 2: the tables, the shareable `meeting` resource and the account data handler;
- 3: the native start and end, §10's end and runs, and billing's count of live meetings;
- 4: the live transcript's store and socket binding for capture, the live and settle sweeps;
- 5: the pipeline's engine and the recovery of runs; stage handlers join in later steps.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.features.billing.contracts import MEETING_MINUTES
from shosai.features.meetings.application.account_data import ACCOUNT_DATA, MeetingsAccountData
from shosai.features.meetings.application.lifecycle import MeetingLifecycle
from shosai.features.meetings.application.live_meetings import LiveMeetingBinder
from shosai.features.meetings.application.live_transcript import LiveTranscript
from shosai.features.meetings.application.minutes import MeetingMinutesCount
from shosai.features.meetings.application.pipeline import PipelineEngine
from shosai.features.meetings.application.run_recovery import RunRecovery
from shosai.features.meetings.application.runs_view import RunViews
from shosai.features.meetings.application.sweeps import MeetingSweeps
from shosai.features.meetings.channels.http.native_sessions import build_native_sessions_router
from shosai.features.meetings.channels.http.runs import build_runs_router
from shosai.features.meetings.channels.tasks import PERIODIC_JOBS, task_handlers
from shosai.features.meetings.contracts import LIVE_MEETINGS, TRANSCRIPT_STORE
from shosai.features.meetings.contracts.events import (
    MeetingDeleted,
    MeetingEnded,
    MeetingRestored,
    NotesReady,
)
from shosai.features.meetings.infrastructure.meeting_records import (
    MEETING_RESOURCE,
    MeetingRecord,
    ParticipantRecord,
    SpeakerRecord,
    TranscriptLineRecord,
)
from shosai.features.meetings.infrastructure.metrics import MeetingMetrics
from shosai.features.meetings.infrastructure.notes_records import (
    FindingRecord,
    FolderRecord,
    NotesRecord,
    SettingsRecord,
    TemplateRecord,
)
from shosai.features.meetings.infrastructure.pipeline_metrics import PipelineMetrics
from shosai.features.meetings.infrastructure.run_records import ObjectDeletionRecord, RunRecord
from shosai.features.meetings.infrastructure.share_records import (
    ShareCommentRecord,
    ShareLinkRecord,
)
from shosai.features.meetings.infrastructure.transcript_metrics import TranscriptMetrics
from shosai.features.meetings.objectives import MEETINGS_MONITORS, MEETINGS_OBJECTIVES


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """The lifecycle and its routes, billing's count and the account data handler."""
    transactions, ports = services.transactions, services.ports
    handler = MeetingsAccountData(transactions, (services.objects, services.uploads))
    pipeline_metrics = PipelineMetrics(services.registry)
    # Обработчики стадий добавляют следующие шаги плана: до них прогоны ждут.
    engine = PipelineEngine(transactions, (services.tasks, pipeline_metrics, {}))
    lifecycle = MeetingLifecycle(
        transactions,
        (ports, services.outbox, MeetingMetrics(services.registry)),
        starter=engine,
    )
    transcript_metrics = TranscriptMetrics(services.registry)
    sweeps = MeetingSweeps(transactions, (ports, lifecycle, transcript_metrics))
    recovery = RunRecovery(transactions, (engine, pipeline_metrics))
    yield FeatureParts(
        http_routers=(
            build_native_sessions_router(lifecycle, ports),
            build_runs_router((lifecycle, RunViews(transactions, ports)), ports),
        ),
        task_handlers=task_handlers(sweeps, (engine, recovery)),
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
        FindingRecord,
        RunRecord,
        ObjectDeletionRecord,
        ShareLinkRecord,
        ShareCommentRecord,
    ),
    events=(MeetingEnded, NotesReady, MeetingDeleted, MeetingRestored),
)

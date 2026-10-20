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
  deletion, and identity's deletion window;
- 9a: the import of recordings with its intake and transcribe stages (`stage_wiring.py`);
- 9b: the native import streamed to the bucket and its job (`channels/http/native_import.py`);
- 10: the speakers of recordings (`application/diarize_stage.py`, `application/align_stage.py`);
- 11: the desktop recording's resumable upload (`channels/http/native_audio.py`);
- 12: the native library and notes, the meetings setting and its `no_logs` mirror;
- 13: the share link and its public page and comments (`channels/http/shared.py`).

The folders' and templates' routes come before `/v1/meetings/{meeting_id}`: the first match
wins, and `folders` is no meeting's id.

Without `MEETINGS_NOTES_MODEL` (development only: production refuses to start) the two
stages have no handler, and runs wait for one.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.features.billing.contracts import MEETING_MINUTES
from shosai.features.identity.contracts import ME_CONTRIBUTIONS
from shosai.features.meetings.application.account_data import ACCOUNT_DATA, MeetingsAccountData
from shosai.features.meetings.application.deletion import MeetingDeletion
from shosai.features.meetings.application.folders import Folders
from shosai.features.meetings.application.hidden_meetings import HiddenMeetings
from shosai.features.meetings.application.import_jobs import ImportJobs
from shosai.features.meetings.application.imports import RecordingImports
from shosai.features.meetings.application.library import MeetingLibrary
from shosai.features.meetings.application.lifecycle import MeetingLifecycle
from shosai.features.meetings.application.live_meetings import LiveMeetingBinder
from shosai.features.meetings.application.live_transcript import LiveTranscript
from shosai.features.meetings.application.meeting_content import MeetingContent
from shosai.features.meetings.application.meeting_settings import MeetingSettings
from shosai.features.meetings.application.minutes import MeetingMinutesCount
from shosai.features.meetings.application.my_notes import MyNotes
from shosai.features.meetings.application.native_imports import NativeImports
from shosai.features.meetings.application.native_library import NativeLibrary
from shosai.features.meetings.application.participants import Participants
from shosai.features.meetings.application.pipeline import PipelineEngine
from shosai.features.meetings.application.recording_uploads import RecordingUploads
from shosai.features.meetings.application.run_recovery import RunRecovery
from shosai.features.meetings.application.runs_view import RunViews
from shosai.features.meetings.application.share_links import ShareLinks
from shosai.features.meetings.application.shared_links import SharedLinks
from shosai.features.meetings.application.shared_pages import SharedPages
from shosai.features.meetings.application.support_meetings import SupportMeetings
from shosai.features.meetings.application.sweeps import MeetingSweeps
from shosai.features.meetings.application.templates import Templates
from shosai.features.meetings.application.write_up_rewrites import WriteUpRewrites
from shosai.features.meetings.channels.http.admin_meetings import build_admin_meetings_router
from shosai.features.meetings.channels.http.folders import build_folders_router
from shosai.features.meetings.channels.http.imports import build_imports_router
from shosai.features.meetings.channels.http.meeting_content import build_meeting_content_router
from shosai.features.meetings.channels.http.meetings import build_meetings_router
from shosai.features.meetings.channels.http.my_notes import build_my_notes_router
from shosai.features.meetings.channels.http.native_audio import build_native_audio_router
from shosai.features.meetings.channels.http.native_import import build_native_import_router
from shosai.features.meetings.channels.http.native_library import build_native_library_router
from shosai.features.meetings.channels.http.native_me_sessions import (
    build_native_me_sessions_router,
)
from shosai.features.meetings.channels.http.native_sessions import build_native_sessions_router
from shosai.features.meetings.channels.http.native_words import NativeWords, load_native_words
from shosai.features.meetings.channels.http.runs import build_runs_router
from shosai.features.meetings.channels.http.settings import build_settings_router
from shosai.features.meetings.channels.http.share_links import build_share_links_router
from shosai.features.meetings.channels.http.shared import build_shared_router
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
from shosai.features.meetings.infrastructure.own_notes_records import OwnNotesRecord
from shosai.features.meetings.infrastructure.part_links import PartLinks, part_client
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
from shosai.features.meetings.stage_wiring import pipeline_stages


def http_routers(
    services: CoreServices,
    pipeline: tuple[MeetingLifecycle, PipelineEngine],
    extras: tuple[PartLinks, NativeWords, MeetingSettings],
) -> tuple[APIRouter, ...]:
    """Meetings' routes; the folders' and templates' come before `/v1/meetings/{meeting_id}`,
    the native import's before `/v1/me/sessions/{session_id}`."""
    transactions, ports = services.transactions, services.ports
    lifecycle, engine = pipeline
    links, words, settings = extras
    library = MeetingLibrary(transactions, ports)
    deletion = MeetingDeletion(transactions, (ports, services.outbox))
    rewrites = WriteUpRewrites(transactions, (ports, services.effects, engine))
    support = SupportMeetings(transactions, (ports, services.outbox))
    imports = RecordingImports(transactions, (ports, engine))
    native_imports = NativeImports(
        transactions, (ports, engine), (services.uploads, services.objects)
    )
    recordings = RecordingUploads(
        transactions, (ports, engine, links), (services.uploads, services.objects)
    )
    my_notes = MyNotes(transactions, ports)
    return (
        build_settings_router(settings, ports),
        build_folders_router(Folders(transactions, services.effects), ports),
        build_templates_router(Templates(transactions, services.effects), ports),
        build_native_sessions_router(lifecycle, ports),
        build_native_import_router(
            (native_imports, ImportJobs(transactions, ports)), ports, services.rate_limiter
        ),
        build_native_audio_router(recordings, ports),
        build_native_library_router((NativeLibrary(transactions, ports), my_notes, words), ports),
        build_native_me_sessions_router((library, deletion), ports),
        build_runs_router((lifecycle, RunViews(transactions, ports)), ports),
        build_write_up_router(rewrites, ports, services.rate_limiter),
        build_meetings_router((library, deletion), ports),
        build_meeting_content_router(MeetingContent(transactions, ports), ports),
        build_my_notes_router((my_notes, Participants(transactions, ports)), ports),
        build_admin_meetings_router(support, ports),
        build_imports_router(imports, ports),
        build_share_links_router(ShareLinks(transactions, ports), ports),
        build_shared_router(
            SharedPages(transactions, (SharedLinks(transactions), ports)), services.rate_limiter
        ),
    )


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """The lifecycle, the pipeline and their routes, billing's count and the account data."""
    transactions, ports = services.transactions, services.ports
    handler = MeetingsAccountData(transactions, (services.objects, services.uploads))
    pipeline_metrics = PipelineMetrics(services.registry)
    # Стадия без обработчика в этом процессе (нет модели или инструментов) ждёт процесса с ним.
    engine = PipelineEngine(
        transactions, (services.tasks, pipeline_metrics, pipeline_stages(services))
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
    settings = MeetingSettings(transactions)
    extras = (load_native_words(), settings)
    async with part_client() as http:
        yield FeatureParts(
            http_routers=http_routers(services, (lifecycle, engine), (PartLinks(http), *extras)),
            task_handlers=task_handlers((sweeps, hidden), (engine, recovery)),
            subscriptions=subscriptions(),
            periodic_jobs=PERIODIC_JOBS,
            provides=(
                ACCOUNT_DATA_HANDLERS.bind(handler),
                MEETING_MINUTES.bind(MeetingMinutesCount()),
                TRANSCRIPT_STORE.bind(LiveTranscript(transactions, transcript_metrics)),
                LIVE_MEETINGS.bind(LiveMeetingBinder(ports)),
                ME_CONTRIBUTIONS.bind(settings),
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

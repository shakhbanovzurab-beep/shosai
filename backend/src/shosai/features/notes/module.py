"""The notes slice as composition sees it (notes plan §3.1), step by step:

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
- 13: the share link and its public page and comments (`channels/http/shared.py`);
- 14: Leo's four read tools over the meetings a person may read (`channels/agent_tools.py`).
- 15a: identity's deletion window serves an account's meetings to nobody, and the readers
  other slices use (`application/meeting_reader.py`);
- 16: Leo's four write tools — a folder, a new write-up, the share link on and off
  (`channels/agent_write_tools.py`).
- 20: the transcript archive of months ended over a year ago and its minute tick, and every
  reader's fallback to it (`application/transcript_archiver.py`).

The folders', counts' and templates' routes come before `/v1/notes/{meeting_id}`: the first
match wins, and `folders` or `counts` is no meeting's id.

Without `NOTES_MODEL` (development only: production refuses to start) the two
stages have no handler, and runs wait for one.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.agent_tools.bindings import AgentTool
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.core.idempotency.action_items import ActionItems
from shosai.features.billing.contracts import MEETING_MINUTES
from shosai.features.identity.contracts import ME_CONTRIBUTIONS
from shosai.features.notes.application.account_data import ACCOUNT_DATA, NotesAccountData
from shosai.features.notes.application.deletion import MeetingDeletion
from shosai.features.notes.application.folders import Folders
from shosai.features.notes.application.hidden_meetings import HiddenMeetings
from shosai.features.notes.application.import_jobs import ImportJobs
from shosai.features.notes.application.imports import RecordingImports
from shosai.features.notes.application.library import MeetingLibrary
from shosai.features.notes.application.library_counts import MeetingCounts
from shosai.features.notes.application.lifecycle import MeetingLifecycle
from shosai.features.notes.application.live_meetings import LiveMeetingBinder
from shosai.features.notes.application.live_transcript import LiveTranscript
from shosai.features.notes.application.meeting_content import MeetingContent
from shosai.features.notes.application.meeting_reader import MeetingsFindings, MeetingsReader
from shosai.features.notes.application.meeting_settings import MeetingSettings
from shosai.features.notes.application.minutes import MeetingMinutesCount
from shosai.features.notes.application.my_notes import MyNotes
from shosai.features.notes.application.native_imports import NativeImports
from shosai.features.notes.application.native_library import NativeLibrary
from shosai.features.notes.application.participants import Participants
from shosai.features.notes.application.pipeline import PipelineEngine
from shosai.features.notes.application.recording_uploads import RecordingUploads
from shosai.features.notes.application.run_recovery import RunRecovery
from shosai.features.notes.application.runs_view import RunViews
from shosai.features.notes.application.share_links import ShareLinks
from shosai.features.notes.application.shared_links import SharedLinks
from shosai.features.notes.application.shared_pages import SharedPages
from shosai.features.notes.application.support_meetings import SupportMeetings
from shosai.features.notes.application.sweeps import MeetingSweeps
from shosai.features.notes.application.templates import Templates
from shosai.features.notes.application.transcript_archiver import TranscriptArchiver
from shosai.features.notes.application.write_up_rewrites import WriteUpRewrites
from shosai.features.notes.channels.agent_link_writes import LinkWrites
from shosai.features.notes.channels.agent_tool_reads import MeetingReads
from shosai.features.notes.channels.agent_tool_writes import NoteWrites, WriteSteps
from shosai.features.notes.channels.agent_tools import READ_TOOLS
from shosai.features.notes.channels.agent_write_tools import WRITE_TOOLS
from shosai.features.notes.channels.http.admin_meetings import build_admin_meetings_router
from shosai.features.notes.channels.http.counts import build_counts_router
from shosai.features.notes.channels.http.folders import build_folders_router
from shosai.features.notes.channels.http.imports import build_imports_router
from shosai.features.notes.channels.http.meeting_content import build_meeting_content_router
from shosai.features.notes.channels.http.meetings import build_meetings_router
from shosai.features.notes.channels.http.my_notes import build_my_notes_router
from shosai.features.notes.channels.http.native_audio import build_native_audio_router
from shosai.features.notes.channels.http.native_import import build_native_import_router
from shosai.features.notes.channels.http.native_library import build_native_library_router
from shosai.features.notes.channels.http.native_me_sessions import (
    build_native_me_sessions_router,
)
from shosai.features.notes.channels.http.native_sessions import build_native_sessions_router
from shosai.features.notes.channels.http.native_words import NativeWords, load_native_words
from shosai.features.notes.channels.http.runs import build_runs_router
from shosai.features.notes.channels.http.settings import build_settings_router
from shosai.features.notes.channels.http.share_links import build_share_links_router
from shosai.features.notes.channels.http.shared import build_shared_router
from shosai.features.notes.channels.http.templates import build_templates_router
from shosai.features.notes.channels.http.write_up import build_write_up_router
from shosai.features.notes.channels.subscriptions import subscriptions
from shosai.features.notes.channels.tasks import PERIODIC_JOBS, task_handlers
from shosai.features.notes.contracts import (
    LIVE_MEETINGS,
    MEETING_FINDINGS,
    MEETING_READER,
    TRANSCRIPT_STORE,
)
from shosai.features.notes.contracts.events import (
    MeetingDeleted,
    MeetingEnded,
    MeetingRestored,
    NotesReady,
)
from shosai.features.notes.infrastructure.archive_metrics import ArchiveMetrics
from shosai.features.notes.infrastructure.meeting_records import (
    MEETING_RESOURCE,
    MeetingRecord,
    ParticipantRecord,
    SpeakerRecord,
    TranscriptLineRecord,
)
from shosai.features.notes.infrastructure.metrics import MeetingMetrics
from shosai.features.notes.infrastructure.notes_records import (
    FindingRecord,
    FolderRecord,
    NotesRecord,
    SettingsRecord,
    TemplateRecord,
)
from shosai.features.notes.infrastructure.own_notes_records import OwnNotesRecord
from shosai.features.notes.infrastructure.part_links import PartLinks, part_client
from shosai.features.notes.infrastructure.pipeline_metrics import PipelineMetrics
from shosai.features.notes.infrastructure.run_objects import RunObjects
from shosai.features.notes.infrastructure.run_records import ObjectDeletionRecord, RunRecord
from shosai.features.notes.infrastructure.share_records import (
    ShareCommentRecord,
    ShareLinkRecord,
)
from shosai.features.notes.infrastructure.transcript_archive import TranscriptArchive
from shosai.features.notes.infrastructure.transcript_metrics import TranscriptMetrics
from shosai.features.notes.objectives import NOTES_MONITORS, NOTES_OBJECTIVES
from shosai.features.notes.settings import NotesSettings, notes_model_set
from shosai.features.notes.stage_wiring import pipeline_stages


def http_routers(
    services: CoreServices,
    pipeline: tuple[MeetingLifecycle, PipelineEngine],
    extras: tuple[PartLinks, NativeWords, MeetingSettings],
) -> tuple[APIRouter, ...]:
    """The slice's routes; the folders' and templates' come before `/v1/notes/{meeting_id}`,
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
    archive = TranscriptArchive(services.objects)
    return (
        build_settings_router(settings, ports),
        build_folders_router(Folders(transactions, services.effects), ports),
        build_counts_router(MeetingCounts(transactions, ports), ports),
        build_templates_router(Templates(transactions, services.effects), ports),
        build_native_sessions_router(lifecycle, ports),
        build_native_import_router(
            (native_imports, ImportJobs(transactions, ports)), ports, services.rate_limiter
        ),
        build_native_audio_router(recordings, ports),
        build_native_library_router(
            (NativeLibrary(transactions, ports, archive), my_notes, words), ports
        ),
        build_native_me_sessions_router((library, deletion), ports),
        build_runs_router((lifecycle, RunViews(transactions, ports)), ports),
        build_write_up_router(rewrites, ports, services.rate_limiter),
        build_meetings_router((library, deletion), ports),
        build_meeting_content_router(MeetingContent(transactions, ports, archive), ports),
        build_my_notes_router((my_notes, Participants(transactions, ports)), ports),
        build_admin_meetings_router(support, ports),
        build_imports_router(imports, ports),
        build_share_links_router(ShareLinks(transactions, ports), ports),
        build_shared_router(
            SharedPages(transactions, (SharedLinks(transactions), ports, archive)),
            services.rate_limiter,
        ),
    )


def agent_tools(services: CoreServices, engine: PipelineEngine) -> tuple[AgentTool, ...]:
    """Leo's four reads and four writes; a write runs once per item key (`ActionItems`)."""
    transactions, ports = services.transactions, services.ports
    steps = WriteSteps(transactions, (ports, ActionItems(services.effects, services.outbox)))
    rewrites = WriteUpRewrites(transactions, (ports, services.effects, engine))
    return (
        *MeetingReads(transactions, ports, TranscriptArchive(services.objects)).bound(),
        *NoteWrites(steps, (MeetingLibrary(transactions, ports), rewrites)).bound(),
        *LinkWrites(steps, ShareLinks(transactions, ports)).bound(),
    )


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """The lifecycle, the pipeline and their routes, billing's count and the account data."""
    transactions, ports = services.transactions, services.ports
    handler = NotesAccountData(transactions, (services.objects, services.uploads))
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
    archive = TranscriptArchive(services.objects)
    archiver = TranscriptArchiver(transactions, (archive, ArchiveMetrics(services.registry)))
    recovery = RunRecovery(transactions, (engine, pipeline_metrics))
    settings = MeetingSettings(transactions)
    extras = (load_native_words(), settings)
    async with part_client() as http:
        yield FeatureParts(
            http_routers=http_routers(services, (lifecycle, engine), (PartLinks(http), *extras)),
            task_handlers=task_handlers((sweeps, hidden, archiver), (engine, recovery)),
            agent_tools=agent_tools(services, engine),
            subscriptions=subscriptions(),
            periodic_jobs=PERIODIC_JOBS,
            provides=(
                ACCOUNT_DATA_HANDLERS.bind(handler),
                MEETING_MINUTES.bind(MeetingMinutesCount()),
                TRANSCRIPT_STORE.bind(LiveTranscript(transactions, transcript_metrics)),
                LIVE_MEETINGS.bind(LiveMeetingBinder(ports)),
                MEETING_READER.bind(MeetingsReader(transactions, ports, archive)),
                MEETING_FINDINGS.bind(MeetingsFindings(ports)),
                ME_CONTRIBUTIONS.bind(settings),
            ),
        )


NOTES = FeatureModule(
    name="notes",
    build=build,
    account_data=(ACCOUNT_DATA,),
    settings=(NotesSettings,),
    production_checks=(notes_model_set,),
    objectives=NOTES_OBJECTIVES,
    monitors=NOTES_MONITORS,
    shareable=(MEETING_RESOURCE,),
    agent_tools=(*READ_TOOLS, *WRITE_TOOLS),
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

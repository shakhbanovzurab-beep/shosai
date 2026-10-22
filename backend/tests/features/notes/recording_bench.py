"""Recordings over the slot's homes and buckets: a real ffmpeg, files' claim, recorded answers.

`video` makes, once per run, a 24 MiB video of 6 min 20 s whose sound pauses 4 seconds in
every 30, so its cut has two parts ending in a pause; `seven_hours` is 2 seconds of sound
whose header claims 7 hours, as a hostile or broken file may. `upload` writes a person's ready
recording upload the way files leaves one — its row and its object under `transient/` —
so the import claims it through files' own claim. The native import (step 9b) streams to
the same buckets, rate-limited over the slot's Valkey, and the desktop's parts (step 11)
go to the bucket's part links; `languages` is each person's language as identity's
profile gives it. Diarization runs on the scripted pyannote, the notes' stages finish at
once, so a run reaches its end. The AI port is the real one over the scripted OpenRouter
and pyannote; the pipeline's engine runs every stage it sent.
"""

import asyncio
import shutil
import struct
import subprocess  # nosec B404 — ffmpeg с постоянными аргументами готовит запись теста
import uuid
from collections.abc import AsyncIterator, Collection, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.calls import ModelRef, ModelRoute, Provider
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.core.storage.port import MultipartUploads, ObjectStorage
from shosai.features.billing.application.minutes import MinutesMeter
from shosai.features.billing.contracts import MINUTES_ALLOWANCE
from shosai.features.files.application.upload_claims import UploadClaims
from shosai.features.files.contracts import UPLOADS
from shosai.features.files.infrastructure.upload_records import UploadRecord
from shosai.features.identity.contracts import (
    ACCOUNT_PROFILE_READER,
    AUTHENTICATOR,
    CONSENT_READER,
    AccountProfile,
)
from shosai.features.notes.application.align_stage import AlignStage
from shosai.features.notes.application.diarize_stage import DiarizeStage
from shosai.features.notes.application.import_jobs import ImportJobs
from shosai.features.notes.application.imports import RecordingImports
from shosai.features.notes.application.intake_stage import IntakeStage
from shosai.features.notes.application.native_imports import NativeImports
from shosai.features.notes.application.pipeline import PipelineEngine, StageHandler, StageWork
from shosai.features.notes.application.recording_uploads import RecordingUploads
from shosai.features.notes.application.stage_task import StageRetryError
from shosai.features.notes.application.transcribe_stage import TranscribeStage
from shosai.features.notes.channels.http.imports import build_imports_router
from shosai.features.notes.channels.http.native_audio import build_native_audio_router
from shosai.features.notes.channels.http.native_import import build_native_import_router
from shosai.features.notes.domain.runs import Stage
from shosai.features.notes.infrastructure.media_tools import MediaLimits, MediaTools
from shosai.features.notes.infrastructure.part_links import PartLinks, part_client
from shosai.features.notes.infrastructure.pipeline_metrics import PipelineMetrics
from shosai.features.workspaces.application.access_policy import WorkspaceAccessPolicy
from shosai.features.workspaces.contracts import ACCESS_POLICY
from shosai.features.workspaces.infrastructure.audit_log import WorkspaceAuditLog
from tests.core.ai.bench import AiBench, Doubles, ai_bench, set_prices, set_rate
from tests.core.storage.adapters import slot_storage
from tests.core.web.probe_app import build_probe_app, client_of
from tests.doubles.business_calendar import MOSCOW
from tests.features.billing.entitlement_bench import Clock, EntitlementBench
from tests.features.billing.people_bench import BearerOfTheTest
from tests.features.notes.library_bench import OUTBOX
from tests.features.notes.notes_bench import Consents, Sent
from tests.harness.database_access import DatabaseAccess
from tests.harness.shared_services import SlotBucket
from tests.support.profiles import names_by_profile

TRANSCRIBE_MODEL: Final = ModelRef(Provider.OPENROUTER, "probe/transcribe")
DIARIZE_MODEL: Final = ModelRef(Provider.PYANNOTE, "precision-3")
VIDEO_SECONDS: Final = 380
CLAIMED_SECONDS: Final = 7 * 3600
LIMITS: Final = MediaLimits(seconds=120, memory_mb=1024)


def ffmpeg(*arguments: str) -> None:
    """Run ffmpeg with the test's own arguments."""
    found = shutil.which("ffmpeg")
    assert found is not None, "для тестов записей нужен ffmpeg на пути"
    subprocess.run([found, "-v", "error", "-y", *arguments], check=True)  # noqa: S603  # nosec B603


@pytest.fixture(scope="session")
def video(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A 24 MiB video whose sound pauses 4 seconds in every 30."""
    target = tmp_path_factory.mktemp("recordings") / "meeting.mp4"
    ffmpeg(
        "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=10",
        "-f", "lavfi", "-i", "sine=frequency=300:sample_rate=44100",
        "-af", "volume=enable='between(mod(t,30),25,29)':volume=0",
        "-t", str(VIDEO_SECONDS), "-c:v", "libx264", "-preset", "ultrafast",
        "-b:v", "460k", "-minrate", "460k", "-maxrate", "460k", "-bufsize", "920k",
        "-c:a", "aac", "-b:a", "64k", str(target),
    )  # fmt: skip
    return target


@pytest.fixture(scope="session")
def seven_hours(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """2 seconds of AAC whose movie, track, media and sample durations claim 7 hours."""
    target = tmp_path_factory.mktemp("recordings") / "long.m4a"
    ffmpeg(
        "-f", "lavfi", "-i", "sine=frequency=300:sample_rate=16000", "-t", "2",
        "-c:a", "aac", "-b:a", "32k", "-movflags", "+faststart", str(target),
    )  # fmt: skip
    body = bytearray(target.read_bytes())
    movie = _stretch(body, b"mvhd")
    _put(body, body.index(b"tkhd") + 24, movie * CLAIMED_SECONDS)
    _put(body, body.index(b"elst") + 12, movie * CLAIMED_SECONDS)
    media = _stretch(body, b"mdhd")
    # Таблица stts: каждой группе кадров даётся длительность, сумма которой — 7 часов.
    at = body.index(b"stts")
    (groups,) = struct.unpack(">I", body[at + 8 : at + 12])
    frames = sum(
        struct.unpack(">I", body[at + 12 + 8 * n : at + 16 + 8 * n])[0] for n in range(groups)
    )
    for n in range(groups):
        _put(body, at + 16 + 8 * n, media * CLAIMED_SECONDS // frames + 1)
    target.write_bytes(body)
    return target


def _stretch(body: bytearray, box: bytes) -> int:
    """Make a version 0 header claim the seconds; its time scale."""
    at = body.index(box)
    (scale,) = struct.unpack(">I", body[at + 16 : at + 20])
    _put(body, at + 20, scale * CLAIMED_SECONDS)
    return int(scale)


def _put(body: bytearray, at: int, value: int) -> None:
    body[at : at + 4] = struct.pack(">I", value)


@dataclass(frozen=True, slots=True)
class RecordingBench:
    """The import route, the engine, the AI double and the slot's buckets."""

    http: httpx.AsyncClient
    homes: DatabaseAccess
    engine: PipelineEngine
    sent: Sent
    ai: AiBench
    storage: Mapping[Home, ObjectStorage]
    minutes: MinutesMeter
    clock: Clock
    languages: Languages
    app: FastAPI

    async def upload(self, owner: uuid.UUID, path: Path, content_type: str) -> uuid.UUID:
        """A ready recording upload of the person's, as files leaves one."""
        upload_id = uuid.uuid4()
        key = f"transient/recording/{upload_id}"
        body = await asyncio.to_thread(path.read_bytes)
        await self.storage[Home.EU].put(key, body, content_type=content_type)
        now = datetime.now(UTC)
        async with self.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
            session.add(
                UploadRecord(
                    id=upload_id, user_id=owner, purpose="recording", object_key=key,
                    multipart_id="done", filename=path.name, content_type=content_type,
                    size_bytes=len(body), state="ready", expires_at=now + timedelta(hours=1),
                )
            )  # fmt: skip
        return upload_id

    async def drive(self, upto: int = 20) -> list[Stage]:
        """Run every stage the engine sent, in order, again when it is given back; the runs."""
        ran: list[Stage] = []
        done = 0
        while done < len(self.sent.payloads) and len(ran) < upto:
            payload = self.sent.payloads[done]
            if not self.engine.handles(payload.stage):
                done += 1
                continue
            ran.append(payload.stage)
            try:
                await self.engine.run_stage(payload)
            except StageRetryError:
                # Брокер доставил бы стадию снова после паузы: стенд делает это сразу.
                continue
            done += 1
        return ran


class NotesSkipped:
    """The notes' stages, another bench's subject: here they finish at once."""

    async def run(self, work: StageWork) -> None:
        """Nothing to write."""
        del work


@dataclass
class Languages:
    """Each person's language, as identity's profile reader gives it; English by default."""

    by_person: dict[uuid.UUID, str] = field(default_factory=dict)

    async def profile(self, session: AsyncSession, user_id: uuid.UUID) -> AccountProfile | None:
        """The person's profile in their language."""
        del session
        return AccountProfile("Person", self.by_person.get(user_id, "en"), None)

    async def names(
        self, session: AsyncSession, user_ids: Collection[uuid.UUID]
    ) -> Mapping[uuid.UUID, str]:
        """Each person's profile name."""
        return await names_by_profile(self.profile, session, user_ids)


def stages(
    homes: DatabaseAccess,
    collaborators: tuple[PortDirectory, Mapping[Home, ObjectStorage]],
    providers: AiBench,
) -> dict[Stage, StageHandler]:
    """The recording's stages over the real tools; the notes' stages finish at once."""
    ports, storage = collaborators
    tools, ai = MediaTools(LIMITS), providers.providers
    return {
        Stage.INTAKE: IntakeStage(homes.transactions, (ports, storage, tools)),
        Stage.TRANSCRIBE: TranscribeStage(
            homes.transactions, (ports, storage, tools), (ai, ModelRoute(TRANSCRIBE_MODEL))
        ),
        Stage.DIARIZE: DiarizeStage(
            homes.transactions, (ports, storage, tools), (ai, ModelRoute(DIARIZE_MODEL))
        ),
        Stage.ALIGN: AlignStage(homes.transactions, storage),
        Stage.FINDINGS: NotesSkipped(),
        Stage.WRITE_UP: NotesSkipped(),
    }


@pytest_asyncio.fixture
async def recording_bench(
    entitlements: EntitlementBench, buckets: Mapping[Home, SlotBucket], valkey: Redis
) -> AsyncIterator[RecordingBench]:
    """Imports of recordings over the slot's homes and buckets."""
    homes, clock = entitlements.homes, entitlements.clock
    await set_prices(homes.transactions, TRANSCRIBE_MODEL, audio_second="0.0000075")
    await set_prices(homes.transactions, DIARIZE_MODEL, audio_second="0.00003")
    await set_rate(homes.transactions, "92.5000")
    providers = ai_bench(homes.transactions, doubles=Doubles())
    ports, sent, languages = PortDirectory(), Sent(), Languages()
    minutes = MinutesMeter(
        homes.transactions, (entitlements.snapshots, ports), clock, business=MOSCOW
    )
    ports.install(
        [
            AUTHENTICATOR.bind(BearerOfTheTest()),
            ACCESS_POLICY.bind(WorkspaceAccessPolicy(OUTBOX, WorkspaceAuditLog())),
            UPLOADS.bind(UploadClaims()),
            MINUTES_ALLOWANCE.bind(minutes),
            CONSENT_READER.bind(Consents()),
            ACCOUNT_PROFILE_READER.bind(languages),
        ]
    )
    slots = {home: slot_storage(bucket) for home, bucket in buckets.items()}
    storage: dict[Home, ObjectStorage] = {home: slot.objects for home, slot in slots.items()}
    uploads: dict[Home, MultipartUploads] = {home: slot.uploads for home, slot in slots.items()}
    handlers = stages(homes, (ports, storage), providers)
    engine = PipelineEngine(
        homes.transactions, (sent, PipelineMetrics(CollectorRegistry()), handlers), clock
    )
    router = build_imports_router(
        RecordingImports(homes.transactions, (ports, engine), clock), ports
    )
    native = build_native_import_router(
        (
            NativeImports(homes.transactions, (ports, engine), (uploads, storage), clock),
            ImportJobs(homes.transactions, ports),
        ),
        ports,
        RateLimiter(valkey, KeyValueMetrics(CollectorRegistry())),
    )
    async with part_client() as part_http:
        recordings = RecordingUploads(
            homes.transactions, (ports, engine, PartLinks(part_http)), (uploads, storage), clock
        )
        audio = build_native_audio_router(recordings, ports)
        app = build_probe_app(extra=(native, audio, router)).app
        async with client_of(app) as http:
            yield RecordingBench(
                http, homes, engine, sent, providers, storage, minutes, clock, languages, app
            )

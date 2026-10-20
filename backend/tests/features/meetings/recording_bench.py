"""Recordings over the slot's homes and buckets: a real ffmpeg, files' claim, recorded answers.

`video` makes, once per run, a 24 MiB video of 6 min 20 s whose sound pauses 4 seconds in
every 30, so its cut has two parts ending in a pause; `seven_hours` is 2 seconds of sound
whose header claims 7 hours, as a hostile or broken file may. `upload` writes a person's ready
recording upload the way files leaves one — its row and its object under `transient/` —
so the import claims it through files' own claim. The AI port is the real one over a
scripted OpenRouter; the pipeline's engine runs the intake and transcribe stages.
"""

import asyncio
import shutil
import struct
import subprocess  # nosec B404 — ffmpeg с постоянными аргументами готовит запись теста
import uuid
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

import httpx
import pytest
import pytest_asyncio
from prometheus_client import CollectorRegistry

from shosai.core.ai.calls import ModelRef, ModelRoute, Provider
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.core.storage.port import ObjectStorage
from shosai.features.billing.application.minutes import MinutesMeter
from shosai.features.billing.contracts import MINUTES_ALLOWANCE
from shosai.features.files.application.upload_claims import UploadClaims
from shosai.features.files.contracts import UPLOADS
from shosai.features.files.infrastructure.upload_records import UploadRecord
from shosai.features.identity.contracts import AUTHENTICATOR, CONSENT_READER
from shosai.features.meetings.application.imports import RecordingImports
from shosai.features.meetings.application.intake_stage import IntakeStage
from shosai.features.meetings.application.pipeline import PipelineEngine, StageHandler
from shosai.features.meetings.application.transcribe_stage import TranscribeStage
from shosai.features.meetings.channels.http.imports import build_imports_router
from shosai.features.meetings.domain.runs import Stage
from shosai.features.meetings.infrastructure.media_tools import MediaLimits, MediaTools
from shosai.features.meetings.infrastructure.pipeline_metrics import PipelineMetrics
from shosai.features.workspaces.application.access_policy import WorkspaceAccessPolicy
from shosai.features.workspaces.contracts import ACCESS_POLICY
from shosai.features.workspaces.infrastructure.audit_log import WorkspaceAuditLog
from tests.core.ai.bench import AiBench, Doubles, ai_bench, set_prices, set_rate
from tests.core.storage.adapters import slot_storage
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.entitlement_bench import Clock, EntitlementBench
from tests.features.billing.people_bench import BearerOfTheTest
from tests.features.meetings.library_bench import OUTBOX
from tests.features.meetings.notes_bench import Consents, Sent
from tests.harness.database_access import DatabaseAccess
from tests.harness.shared_services import SlotBucket

TRANSCRIBE_MODEL: Final = ModelRef(Provider.OPENROUTER, "probe/transcribe")
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

    async def drive(self, upto: int = 10) -> list[Stage]:
        """Run every stage the engine sent, in order; the stages it ran."""
        ran: list[Stage] = []
        done = 0
        while done < len(self.sent.payloads) and len(ran) < upto:
            payload = self.sent.payloads[done]
            done += 1
            if self.engine.handles(payload.stage):
                await self.engine.run_stage(payload)
                ran.append(payload.stage)
        return ran


def stages(
    homes: DatabaseAccess,
    collaborators: tuple[PortDirectory, Mapping[Home, ObjectStorage]],
    providers: AiBench,
) -> dict[Stage, StageHandler]:
    """The intake and transcribe stages over the real tools."""
    ports, storage = collaborators
    tools = MediaTools(LIMITS)
    route = ModelRoute(TRANSCRIBE_MODEL)
    return {
        Stage.INTAKE: IntakeStage(homes.transactions, (ports, storage, tools)),
        Stage.TRANSCRIBE: TranscribeStage(
            homes.transactions, (ports, storage, tools), (providers.providers, route)
        ),
    }


@pytest_asyncio.fixture
async def recording_bench(
    entitlements: EntitlementBench, buckets: Mapping[Home, SlotBucket]
) -> AsyncIterator[RecordingBench]:
    """Imports of recordings over the slot's homes and buckets."""
    homes, clock = entitlements.homes, entitlements.clock
    await set_prices(homes.transactions, TRANSCRIBE_MODEL, audio_second="0.0000075")
    await set_rate(homes.transactions, "92.5000")
    providers = ai_bench(homes.transactions, doubles=Doubles())
    ports, sent = PortDirectory(), Sent()
    minutes = MinutesMeter(homes.transactions, (entitlements.snapshots, ports), clock)
    ports.install(
        [
            AUTHENTICATOR.bind(BearerOfTheTest()),
            ACCESS_POLICY.bind(WorkspaceAccessPolicy(OUTBOX, WorkspaceAuditLog())),
            UPLOADS.bind(UploadClaims()),
            MINUTES_ALLOWANCE.bind(minutes),
            CONSENT_READER.bind(Consents()),
        ]
    )
    storage: dict[Home, ObjectStorage] = {
        home: slot_storage(bucket).objects for home, bucket in buckets.items()
    }
    handlers = stages(homes, (ports, storage), providers)
    engine = PipelineEngine(
        homes.transactions, (sent, PipelineMetrics(CollectorRegistry()), handlers), clock
    )
    router = build_imports_router(
        RecordingImports(homes.transactions, (ports, engine), clock), ports
    )
    async with client_of(build_probe_app(extra=(router,)).app) as http:
        yield RecordingBench(http, homes, engine, sent, providers, storage, minutes, clock)

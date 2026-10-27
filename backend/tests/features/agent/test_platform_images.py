"""Pictures Leo draws for the platform operator (agent step 16b2, AG-D5, AG-D10): drawn by the
image model at the platform's cost, stored as a platform object with its pointer, handed over
by reference, read by the admin through a short link, and released with their thread."""

import uuid
import zlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from io import BytesIO

import httpx
from PIL import Image
from prometheus_client import CollectorRegistry

from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import ToolErrorCode
from shosai.core.agent_tools.sources import ArtifactKind, ArtifactRef
from shosai.core.ai.calls import CallContext, ModelRef, ModelRoute, PlatformAccount, Provider
from shosai.core.ai.requests import ImageRequest
from shosai.core.ai.results import GeneratedImage, Usage
from shosai.core.config.roles import ProcessRole
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.core.storage.port import ObjectStorage
from shosai.features.agent.application.platform_images import DrawImageIn, PlatformImages
from shosai.features.agent.application.threads import Threads
from shosai.features.agent.application.tool_round import artifact_of
from shosai.features.agent.channels.http.callers import operator_mount
from shosai.features.agent.channels.http.images import build_images_router
from shosai.features.agent.channels.http.threads import ARTIFACTS, ImageArtifactOut
from shosai.features.agent.channels.platform_tools import operator_only
from shosai.features.agent.domain.operator import OPERATOR_ID, operator_scope
from shosai.features.agent.domain.threads import ScopeKind, ThreadScope
from shosai.features.agent.infrastructure.run_records import AgentRunRecord
from shosai.features.identity.contracts import ADMIN_GATE, Principal
from shosai.features.workspaces.contracts import MEMBERSHIP_READER
from shosai.features.workspaces.infrastructure.membership_reader import MembershipDirectory
from tests.core.storage.adapters import slot_storage
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.agent.turn_doubles import ADMIN_SESSION, AdminSession
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot
from tests.harness.shared_services import SlotBucket

ROUTE = ModelRoute(ModelRef(Provider.OPENROUTER, "probe/painter"))
DRAW = DrawImageIn(prompt="A calm study with a desk by the window.", caption="Кабинет у окна")


def png(width: int = 64, height: int = 48) -> bytes:
    """A small PNG."""
    out = BytesIO()
    Image.new("RGB", (width, height), "white").save(out, format="PNG")
    return out.getvalue()


def claiming(width: int, height: int) -> bytes:
    """A PNG whose header claims a size its pixels do not have: read without decoding."""
    data = bytearray(png(1, 1))
    header = b"IHDR" + width.to_bytes(4, "big") + height.to_bytes(4, "big") + bytes(data[24:29])
    data[12:29] = header
    data[29:33] = zlib.crc32(header).to_bytes(4, "big")
    return bytes(data)


@dataclass
class Painter:
    """The image model: the picture it returns, and the calls it took."""

    picture: GeneratedImage = field(
        default_factory=lambda: GeneratedImage(png(), "image/png", ROUTE.primary, Usage())
    )
    calls: list[CallContext] = field(default_factory=list)

    async def generate_image(
        self, context: CallContext, route: ModelRoute, request: ImageRequest
    ) -> GeneratedImage:
        """The test's picture."""
        del route, request
        self.calls.append(context)
        return self.picture


def images_of(
    homes: DatabaseAccess,
    buckets: Mapping[Home, SlotBucket],
    painter: Painter,
    *,
    routed: bool = True,
) -> tuple[PlatformImages, Mapping[Home, ObjectStorage]]:
    """The pictures over the slot's homes and buckets."""
    objects = {home: slot_storage(bucket).objects for home, bucket in buckets.items()}
    route = ROUTE if routed else None
    return PlatformImages(homes.transactions, objects, (painter, lambda: route)), objects


async def operator_run(homes: DatabaseAccess) -> tuple[uuid.UUID, uuid.UUID]:
    """An operator's thread with one run: their ids."""
    ports = PortDirectory()
    ports.install([MEMBERSHIP_READER.bind(MembershipDirectory())])
    threads = Threads(
        homes.transactions, (ports, EffectLedger(EffectKeyMetrics(CollectorRegistry())))
    )
    scope = operator_scope()
    principal = Principal(OPERATOR_ID, scope.home, 0)
    thread = await threads.create(principal, ThreadScope(ScopeKind.PERSONAL), f"t:{uuid.uuid4()}")
    run_id = uuid.uuid4()
    async with homes.transactions.begin(scope) as session:
        session.add(
            AgentRunRecord(
                id=run_id, started_at=datetime.now(UTC), thread_id=thread.id,
                user_id=principal.user_id, channel="admin", language="ru", status="running",
                token_route="within_allowance",
            )
        )  # fmt: skip
    return thread.id, run_id


def context_of(run_id: uuid.UUID, scope: TenancyScope | None = None) -> ToolContext:
    """The tool call's context, the operator's by default."""
    deadline = datetime.now(UTC) + timedelta(minutes=2)
    return ToolContext(scope or operator_scope(), run_id, deadline)


async def test_a_picture_is_drawn_at_the_platform_s_cost_kept_by_reference_and_linked(
    homes: DatabaseAccess, buckets: Mapping[Home, SlotBucket]
) -> None:
    painter = Painter()
    images, objects = images_of(homes, buckets, painter)
    _, run_id = await operator_run(homes)

    result = await images.draw(DRAW, context_of(run_id))
    assert result.output is not None
    image_id = uuid.UUID(result.output.image_id)
    link = await images.link(operator_scope(), image_id)
    assert link is not None
    async with httpx.AsyncClient() as client:
        fetched = await client.get(link)

    [artifact] = result.artifacts
    assert (artifact.kind, artifact.ref, artifact.alt) == (
        ArtifactKind.IMAGE,
        str(image_id),
        DRAW.caption,
    )
    assert artifact.fields == {"width": "64", "height": "48"}
    [call] = painter.calls
    assert (call.platform_account, call.scope) == (PlatformAccount.ADMIN_ASSISTANT, None)
    assert (fetched.status_code, fetched.content) == (200, painter.picture.data)
    assert fetched.headers["content-type"] == "image/png"
    assert await objects[Home.EU].head(f"platform/agent/images/{image_id}") is not None
    assert await images.link(TenancyScope(Home.EU, uuid.uuid4()), image_id) is None


async def test_no_model_no_picture_or_a_person_leaves_nothing_behind(
    homes: DatabaseAccess, buckets: Mapping[Home, SlotBucket]
) -> None:
    _, run_id = await operator_run(homes)
    unrouted, _ = images_of(homes, buckets, Painter(), routed=False)
    text = Painter(GeneratedImage(b"not a picture", "image/png", ROUTE.primary, Usage()))
    lying = Painter(GeneratedImage(png(), "image/jpeg", ROUTE.primary, Usage()))
    huge = Painter(GeneratedImage(claiming(10_000, 5_000), "image/png", ROUTE.primary, Usage()))
    person = TenancyScope(Home.EU, uuid.uuid4())

    codes = [
        (await images.draw(DRAW, context_of(run_id))).error
        for images in (
            unrouted,
            images_of(homes, buckets, text)[0],
            images_of(homes, buckets, lying)[0],
            images_of(homes, buckets, huge)[0],
        )
    ]
    guarded = operator_only(images_of(homes, buckets, Painter())[0].draw)
    refused = await guarded(DRAW, context_of(run_id, person))

    assert [error.code if error else None for error in codes] == [ToolErrorCode.UNAVAILABLE] * 4
    assert refused.error is not None
    assert refused.error.code is ToolErrorCode.FORBIDDEN
    [objects] = [images_of(homes, buckets, Painter())[1]]
    assert [info async for info in objects[Home.EU].list_objects("platform/agent/images/")] == []


async def test_the_admin_reads_it_by_redirect_and_it_goes_with_its_thread(
    homes: DatabaseAccess, buckets: Mapping[Home, SlotBucket], run_slot: RunSlot
) -> None:
    images, objects = images_of(homes, buckets, Painter())
    thread_id, run_id = await operator_run(homes)
    drawn = await images.draw(DRAW, context_of(run_id))
    assert drawn.output is not None
    image_id = drawn.output.image_id
    ports = PortDirectory()
    ports.install([ADMIN_GATE.bind(AdminSession()), MEMBERSHIP_READER.bind(MembershipDirectory())])
    app = build_probe_app(extra=(build_images_router(images, operator_mount(ports)),)).app
    async with client_of(app) as http:
        admitted = await http.get(
            f"/v1/admin/agent/images/{image_id}",
            headers={"Cookie": f"shosai_admin={ADMIN_SESSION}"},
        )
        anonymous = await http.get(f"/v1/admin/agent/images/{image_id}")
        missing = await http.get(
            f"/v1/admin/agent/images/{uuid.uuid4()}",
            headers={"Cookie": f"shosai_admin={ADMIN_SESSION}"},
        )

    threads = Threads(
        homes.transactions, (ports, EffectLedger(EffectKeyMetrics(CollectorRegistry())))
    )
    await threads.delete(Principal(OPERATOR_ID, operator_scope().home, 0), thread_id)
    shape = ProcessShape(role=ProcessRole.WORKERS)
    async with open_database_access(slot_urls(run_slot), shape) as workers:
        released = await PlatformImages(
            workers.transactions, objects, (Painter(), lambda: ROUTE)
        ).release(Home.EU)
        again = await PlatformImages(
            workers.transactions, objects, (Painter(), lambda: ROUTE)
        ).release(Home.EU)

    assert (admitted.status_code, admitted.headers["cache-control"]) == (302, "no-store")
    assert admitted.headers["location"].startswith("http")
    assert (anonymous.status_code, missing.status_code) == (401, 404)
    assert missing.json()["detail"] == "image_not_found"
    assert (released, again) == (1, 0)
    assert await objects[Home.EU].head(f"platform/agent/images/{image_id}") is None


def test_the_stream_and_the_history_carry_a_picture_with_its_size_in_pixels() -> None:
    artifact = ArtifactRef(ArtifactKind.IMAGE, "pic-1", "Кабинет", {"width": "64", "height": "48"})

    carried = artifact_of(artifact)
    read = ARTIFACTS.validate_python(carried)

    assert carried == {"kind": "image", "ref": "pic-1", "alt": "Кабинет", "width": 64, "height": 48}
    assert isinstance(read, ImageArtifactOut)
    assert (read.width, read.height) == (64, 48)

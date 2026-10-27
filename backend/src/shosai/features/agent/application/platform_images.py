"""Pictures Leo draws for the platform operator (AG-D5, AG-D10; agent step 16b2).

`images.draw` asks the image model (`AGENT_IMAGE_MODEL`, paid by the platform's
`admin_assistant` account) for a picture, checks its type, weight and size, stores the object
under `platform/agent/images/` in the EU home's bucket and its pointer row by the run, and
hands the answer an `image` artifact by reference — never the bytes. The admin panel reads it
through a 15-minute link. A thread's deletion releases its pictures' objects (a trigger), and
the release tick deletes them as the sweep role, then their release rows.
"""

from collections.abc import Callable, Mapping
from datetime import timedelta
from typing import Final, Protocol
from uuid import UUID

import structlog
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select

from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import ToolErrorCode, ToolResult
from shosai.core.agent_tools.sources import ArtifactKind, ArtifactRef
from shosai.core.ai.calls import CallClass, CallContext, CallOrigin, ModelRoute
from shosai.core.ai.errors import AiCallError
from shosai.core.ai.requests import ImageRequest
from shosai.core.ai.results import GeneratedImage
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.storage.port import Disposition, ObjectStorage
from shosai.features.agent.domain.images import (
    BYTES_MAX,
    CAPTION_MAX,
    IMAGE_TYPES,
    PROMPT_MAX,
    extension_of,
    image_key,
)
from shosai.features.agent.domain.operator import OPERATOR_HOME, payer_of
from shosai.features.agent.infrastructure.image_records import (
    AgentImageRecord,
    AgentImageReleaseRecord,
)
from shosai.features.agent.infrastructure.image_sizes import ImageRefusedError, image_size

FEATURE: Final = "agent.image"
DEADLINE: Final = timedelta(seconds=90)
# За один тик освобождается не больше: остальное — следующим.
RELEASE_BATCH: Final = 500
log = structlog.stdlib.get_logger(__name__)


class DrawImageIn(BaseModel):
    """What to draw, and its caption."""

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(
        min_length=1, max_length=PROMPT_MAX,
        description="What the picture shows, in detail; in English for the best result.",
    )  # fmt: skip
    caption: str = Field(
        min_length=1, max_length=CAPTION_MAX,
        description="A short caption in Russian, read by those who do not see the picture.",
    )  # fmt: skip


class DrawImageOut(BaseModel):
    """The picture drawn, shown to the operator under the answer."""

    image_id: str
    width: int
    height: int


class ImageMaker(Protocol):
    """What the pictures need of the provider port."""

    async def generate_image(
        self, context: CallContext, route: ModelRoute, request: ImageRequest
    ) -> GeneratedImage:
        """A picture from a prompt."""
        ...


class PlatformImages:
    """Draws, links and releases the operator's pictures."""

    def __init__(
        self,
        transactions: HomeTransactions,
        objects: Mapping[Home, ObjectStorage],
        drawing: tuple[ImageMaker, Callable[[], ModelRoute | None]],
    ) -> None:
        self._transactions = transactions
        self._objects = objects
        self._ai, self._route = drawing

    async def draw(self, arguments: DrawImageIn, context: ToolContext) -> ToolResult[DrawImageOut]:
        """A picture of the prompt, stored and handed over by reference."""
        route = self._route()
        if route is None:
            return ToolResult.failed(ToolErrorCode.UNAVAILABLE)
        image_id = new_id()
        scope, platform = payer_of(context.scope)
        call = CallContext(
            effect_key=f"{FEATURE}:{image_id}", feature=FEATURE, call_class=CallClass.EXPENSIVE,
            origin=CallOrigin.INTERACTIVE, scope=scope, platform_account=platform,
            deadline=DEADLINE,
        )  # fmt: skip
        try:
            image = await self._ai.generate_image(call, route, ImageRequest(arguments.prompt))
        except AiCallError as failed:
            log.warning("Картинка оператора не нарисована", failure=failed.code)
            return ToolResult.failed(ToolErrorCode.UNAVAILABLE)
        try:
            width, height = checked(image)
        except ImageRefusedError:
            log.warning("Модель вернула не картинку", media_type=image.media_type)
            return ToolResult.failed(ToolErrorCode.UNAVAILABLE)
        await self._store(context, image_id, image, (width, height))
        artifact = ArtifactRef(
            ArtifactKind.IMAGE, str(image_id), arguments.caption,
            {"width": str(width), "height": str(height)},
        )  # fmt: skip
        out = DrawImageOut(image_id=str(image_id), width=width, height=height)
        return ToolResult(out, artifacts=(artifact,))

    async def link(self, scope: TenancyScope, image_id: UUID) -> str | None:
        """A 15-minute link to the operator's picture, or None when it is gone."""
        async with self._transactions.begin(scope, read_only=True) as session:
            record = await session.scalar(
                select(AgentImageRecord).where(
                    AgentImageRecord.id == image_id, AgentImageRecord.user_id == scope.user_id
                )
            )
        if record is None:
            return None
        name = f"leo-{image_id}.{extension_of(record.content_type)}"
        signed = await self._objects[scope.home].presign_get(
            record.object_key, filename=name, disposition=Disposition.INLINE,
            content_type=record.content_type,
        )  # fmt: skip
        return signed.url

    async def release(self, home: Home) -> int:
        """Delete the released objects of the home, then their rows, as the sweep role; how
        many went."""
        async with self._transactions.begin(
            TenancyScope(home), read_only=True, sweep=True
        ) as session:
            keys = list(
                await session.scalars(
                    select(AgentImageReleaseRecord.object_key)
                    .order_by(AgentImageReleaseRecord.created_at)
                    .limit(RELEASE_BATCH)
                )
            )
        if not keys:
            return 0
        await self._objects[home].delete_many(keys)
        async with self._transactions.begin(TenancyScope(home), sweep=True) as session:
            await session.execute(
                delete(AgentImageReleaseRecord).where(AgentImageReleaseRecord.object_key.in_(keys))
            )
        log.info("Объекты удалённых картинок оператора удалены", home=home.value, count=len(keys))
        return len(keys)

    async def _store(
        self, context: ToolContext, image_id: UUID, image: GeneratedImage, size: tuple[int, int]
    ) -> None:
        key = image_key(image_id)
        await self._objects[OPERATOR_HOME].put(key, image.data, content_type=image.media_type)
        try:
            async with self._transactions.begin(context.scope) as session:
                session.add(
                    AgentImageRecord(
                        id=image_id, user_id=context.scope.user_id, run_id=context.run_id,
                        object_key=key, content_type=image.media_type,
                        size_bytes=len(image.data), width=size[0], height=size[1],
                    )
                )  # fmt: skip
        except BaseException:
            # Строка не записана: объект без указателя удаляется сразу (ADR 0055 п. 3).
            await self._objects[OPERATOR_HOME].delete(key)
            raise


def checked(image: GeneratedImage) -> tuple[int, int]:
    """The picture's size, once its type and weight are the panel's."""
    if image.media_type not in IMAGE_TYPES or not 0 < len(image.data) <= BYTES_MAX:
        raise ImageRefusedError
    return image_size(image.data, image.media_type)

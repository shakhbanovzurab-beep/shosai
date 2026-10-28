"""Leo's `studio` toolset: the person's own words about themselves, read and rewritten (step 13).

`studio.read_context` reads what the person wrote in Studio's "About you"; it is their own text,
so it carries no provenance. `studio.update_context` rewrites it whole on a card that shows the
new text: the person approves it first, it is applied once, and they can change it back in
Studio, so the write is compensable. The write is never offered over MCP: an external agent does
not rewrite what Leo knows about the person (studio plan §3.2).
"""

from datetime import datetime, timedelta
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from shosai.core.agent_tools.spec import Reversibility, ToolEffect, ToolSpec
from shosai.features.studio.channels import agent_previews as words
from shosai.features.studio.domain.prompts import CONTEXT_MAX

TOOLSET: Final = "studio"
# Клиентский домен запросов кабинета, который перечитывается после записи.
STUDIO_DOMAIN: Final = ("studio",)


class Strict(BaseModel):
    """Tool arguments: a field the schema lacks is refused."""

    model_config = ConfigDict(extra="forbid")


class ReadContext(Strict):
    """Reading the user's own words takes no arguments."""


class PersonalContext(BaseModel):
    """What the user wrote about themselves in Studio."""

    content: str = Field(description="The user's own words; empty when they wrote none.")
    updated_at: datetime | None = Field(description="When they last changed it; null if never.")


class UpdateContext(Strict):
    """Arguments of rewriting the user's words about themselves."""

    content: str = Field(
        max_length=CONTEXT_MAX,
        description=(
            "The whole new text of what the user wants Leo to know about them, at most 4000"
            " characters; it replaces the old text, so keep what they did not ask to change."
        ),
    )


class ContextUpdated(BaseModel):
    """The text the user's Studio now holds."""

    content: str = Field(description="The new text, as stored (trimmed).")
    updated_at: datetime = Field(description="When it was saved.")


READ_CONTEXT: Final = ToolSpec(
    name="studio.read_context", toolset=TOOLSET,
    description=(
        "Read what the user wrote about themselves in Studio's \"About you\": the words every"
        " answer to them takes into account. Use it before changing it, or when the user asks"
        " what Leo knows about them from Studio."
    ),
    input=ReadContext, output=PersonalContext, effect=ToolEffect.READ,
    result_budget=3_000, timeout=timedelta(seconds=5),
)  # fmt: skip
UPDATE_CONTEXT: Final = ToolSpec(
    name="studio.update_context", toolset=TOOLSET,
    description=(
        "Rewrite what the user wrote about themselves in Studio's \"About you\", when they ask"
        " you to remember something about themselves there or to change it. Read it first with"
        " studio.read_context and send the whole new text. The user approves a card with the"
        " new text first; they can change it back in Studio."
    ),
    input=UpdateContext, output=ContextUpdated, effect=ToolEffect.WRITE,
    reversibility=Reversibility.COMPENSABLE, result_budget=3_000, timeout=timedelta(seconds=10),
    invalidates=STUDIO_DOMAIN, previews=(words.UPDATE_CONTEXT,), mcp=False,
)  # fmt: skip
STUDIO_TOOLS: Final = (READ_CONTEXT, UPDATE_CONTEXT)
